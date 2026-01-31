"""Integration tests for prompt analytics data pipeline.

Tests verify:
1. otel_traces → InferenceFact (MV transformations)
2. InferenceFact → InferenceMetrics5m/1h/1d (rollup aggregations)

CRITICAL: If tests fail, it indicates MV bugs. DO NOT adjust ground_truth functions.

Architecture:
- Seeder JSON is SINGLE SOURCE OF TRUTH
- ground_truth.py functions DERIVE expected values from seeder
- Tests assert actual DB results against derived expected values
"""

import json
import time

import pytest

from .conftest import (
    clear_all_tables,
    execute_query,
    load_test_data,
    query_inference_fact,
    query_inference_fact_by_trace,
    seed_otel_traces,
)
from .ground_truth import (
    SKIP_COLUMNS,
    compare_values,
    get_expected_blocked_count,
    get_expected_cached_count,
    get_expected_dimension_values,
    get_expected_endpoint_type_counts,
    get_expected_finish_reason_counts,
    get_expected_inference_fact,
    get_expected_model_values,
    get_expected_performance_totals,
    get_expected_prompt_analytics_counts,
    get_expected_prompt_analytics_values,
    get_expected_rollup_totals,
    get_expected_row_count,
    get_expected_rows_with_tokens,
)


# =============================================================================
# AGGREGATE OUTCOME TESTS (Primary - seed ALL data, test aggregate outcomes)
# =============================================================================


@pytest.mark.integration
class TestInferenceFactCounts:
    """Test aggregate counts in InferenceFact derived from seeder."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Seed ALL test data."""
        clear_all_tables()
        result = seed_otel_traces()  # ALL scenarios
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(1)  # Wait for MVs
        yield

    def test_total_row_count(self):
        """Total InferenceFact rows == expected from seeder."""
        expected_count = get_expected_row_count(self.seeder_data)
        actual_count = int(execute_query("SELECT count() FROM InferenceFact"))
        assert actual_count == expected_count, (
            f"Row count: expected={expected_count}, actual={actual_count}"
        )

    def test_success_count(self):
        """Count of is_success=true matches seeder."""
        expected = get_expected_rollup_totals(self.seeder_data)
        actual = int(execute_query("SELECT count() FROM InferenceFact WHERE is_success = true"))
        assert actual == expected["success_count"], (
            f"Success count: expected={expected['success_count']}, actual={actual}"
        )

    def test_error_count(self):
        """Count of is_success=false matches seeder."""
        expected = get_expected_rollup_totals(self.seeder_data)
        actual = int(execute_query("SELECT count() FROM InferenceFact WHERE is_success = false"))
        assert actual == expected["error_count"], (
            f"Error count: expected={expected['error_count']}, actual={actual}"
        )

    def test_blocked_count(self):
        """Count of is_blocked=true matches seeder."""
        expected = get_expected_blocked_count(self.seeder_data)
        actual = int(execute_query("SELECT count() FROM InferenceFact WHERE is_blocked = true"))
        assert actual == expected, f"Blocked count: expected={expected}, actual={actual}"

    def test_no_duplicate_inference_ids(self):
        """No duplicate inference_ids (cross-product check)."""
        total = int(execute_query(
            "SELECT count() FROM InferenceFact WHERE inference_id IS NOT NULL"
        ))
        unique = int(execute_query(
            "SELECT count(DISTINCT inference_id) FROM InferenceFact WHERE inference_id IS NOT NULL"
        ))
        assert total == unique, f"Duplicate inference_ids found: total={total}, unique={unique}"


@pytest.mark.integration
class TestInferenceFactTokenMetrics:
    """Test token metrics in InferenceFact derived from seeder."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_all_tables()
        result = seed_otel_traces()
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(1)
        yield

    def test_input_tokens_sum(self):
        """Sum of input_tokens matches seeder."""
        expected = get_expected_rollup_totals(self.seeder_data)
        actual = int(execute_query("SELECT sum(ifNull(input_tokens, 0)) FROM InferenceFact"))
        assert actual == expected["total_input_tokens"], (
            f"Input tokens sum: expected={expected['total_input_tokens']}, actual={actual}"
        )

    def test_output_tokens_sum(self):
        """Sum of output_tokens matches seeder."""
        expected = get_expected_rollup_totals(self.seeder_data)
        actual = int(execute_query("SELECT sum(ifNull(output_tokens, 0)) FROM InferenceFact"))
        assert actual == expected["total_output_tokens"], (
            f"Output tokens sum: expected={expected['total_output_tokens']}, actual={actual}"
        )

    def test_input_tokens_not_null_where_expected(self):
        """Rows with expected input_tokens have non-NULL values."""
        expected_with_tokens = get_expected_rows_with_tokens(self.seeder_data)
        actual_with_tokens = int(execute_query(
            "SELECT count() FROM InferenceFact WHERE input_tokens IS NOT NULL"
        ))
        assert actual_with_tokens >= expected_with_tokens, (
            f"Rows with input_tokens: expected>={expected_with_tokens}, actual={actual_with_tokens}"
        )


@pytest.mark.integration
class TestInferenceFactPerformanceMetrics:
    """Test performance metrics in InferenceFact derived from seeder."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_all_tables()
        result = seed_otel_traces()
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(1)
        yield

    def test_response_time_sum(self):
        """Sum of response_time_ms matches seeder."""
        expected = get_expected_performance_totals(self.seeder_data)
        actual = int(execute_query("SELECT sum(ifNull(response_time_ms, 0)) FROM InferenceFact"))
        assert actual == expected["total_response_time_ms"], (
            f"Response time sum: expected={expected['total_response_time_ms']}, actual={actual}"
        )

    def test_ttft_sum(self):
        """Sum of ttft_ms matches seeder."""
        expected = get_expected_performance_totals(self.seeder_data)
        actual = int(execute_query("SELECT sum(ifNull(ttft_ms, 0)) FROM InferenceFact"))
        assert actual == expected["total_ttft_ms"], (
            f"TTFT sum: expected={expected['total_ttft_ms']}, actual={actual}"
        )

    def test_processing_time_sum(self):
        """Sum of processing_time_ms matches seeder."""
        expected = get_expected_performance_totals(self.seeder_data)
        actual = int(execute_query("SELECT sum(ifNull(processing_time_ms, 0)) FROM InferenceFact"))
        assert actual == expected["total_processing_time_ms"], (
            f"Processing time sum: expected={expected['total_processing_time_ms']}, actual={actual}"
        )

    def test_gateway_processing_sum(self):
        """Sum of gateway_processing_ms matches seeder."""
        expected = get_expected_performance_totals(self.seeder_data)
        actual = int(execute_query(
            "SELECT sum(ifNull(gateway_processing_ms, 0)) FROM InferenceFact"
        ))
        assert actual == expected["total_gateway_processing_ms"], (
            f"Gateway processing sum: expected={expected['total_gateway_processing_ms']}, "
            f"actual={actual}"
        )

    def test_total_duration_sum(self):
        """Sum of total_duration_ms matches seeder."""
        expected = get_expected_performance_totals(self.seeder_data)
        actual = int(execute_query("SELECT sum(ifNull(total_duration_ms, 0)) FROM InferenceFact"))
        assert actual == expected["total_duration_ms"], (
            f"Total duration sum: expected={expected['total_duration_ms']}, actual={actual}"
        )


@pytest.mark.integration
class TestInferenceFactDimensionUUIDs:
    """Test dimension UUIDs in InferenceFact match seeder."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_all_tables()
        result = seed_otel_traces()
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(1)
        yield

    def test_project_ids_match(self):
        """All project_id values match seeder."""
        expected_ids = get_expected_dimension_values(self.seeder_data, "project_id")
        result = execute_query(
            "SELECT DISTINCT toString(project_id) FROM InferenceFact "
            "WHERE project_id IS NOT NULL"
        )
        actual_ids = set(result.split('\n')) if result else set()
        assert expected_ids <= actual_ids, f"Missing project_ids: {expected_ids - actual_ids}"

    def test_endpoint_ids_match(self):
        """All endpoint_id values match seeder."""
        expected_ids = get_expected_dimension_values(self.seeder_data, "endpoint_id")
        if not expected_ids:
            pytest.skip("No endpoint_ids in seeder")
        result = execute_query(
            "SELECT DISTINCT toString(endpoint_id) FROM InferenceFact "
            "WHERE endpoint_id IS NOT NULL"
        )
        actual_ids = set(result.split('\n')) if result else set()
        assert expected_ids <= actual_ids, f"Missing endpoint_ids: {expected_ids - actual_ids}"


@pytest.mark.integration
class TestInferenceFactEndpointTypes:
    """Test endpoint_type distribution matches seeder."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_all_tables()
        result = seed_otel_traces()
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(1)
        yield

    def test_endpoint_type_counts(self):
        """Count per endpoint_type matches seeder."""
        expected_counts = get_expected_endpoint_type_counts(self.seeder_data)
        result = execute_query(
            "SELECT endpoint_type, count() as cnt FROM InferenceFact "
            "GROUP BY endpoint_type FORMAT JSONEachRow"
        )
        actual_counts = {}
        if result:
            for line in result.split('\n'):
                if line:
                    row = json.loads(line)
                    actual_counts[row["endpoint_type"]] = int(row["cnt"])

        for ep_type, expected_cnt in expected_counts.items():
            actual_cnt = actual_counts.get(ep_type, 0)
            assert actual_cnt == expected_cnt, (
                f"endpoint_type={ep_type}: expected={expected_cnt}, actual={actual_cnt}"
            )


@pytest.mark.integration
class TestInferenceFactPromptAnalytics:
    """Test prompt analytics fields match seeder."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_all_tables()
        result = seed_otel_traces()
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(1)
        yield

    def test_prompt_id_count(self):
        """Count of rows with prompt_id matches seeder."""
        expected = get_expected_prompt_analytics_counts(self.seeder_data)
        actual = int(execute_query(
            "SELECT count() FROM InferenceFact "
            "WHERE prompt_id IS NOT NULL AND prompt_id != ''"
        ))
        assert actual == expected["with_prompt_id"], (
            f"Rows with prompt_id: expected={expected['with_prompt_id']}, actual={actual}"
        )

    def test_unique_prompt_ids(self):
        """All expected prompt_id values present."""
        expected_ids = get_expected_rollup_totals(self.seeder_data)["unique_prompt_ids"]
        if not expected_ids:
            pytest.skip("No prompt_ids in seeder")
        result = execute_query(
            "SELECT DISTINCT prompt_id FROM InferenceFact "
            "WHERE prompt_id IS NOT NULL AND prompt_id != ''"
        )
        actual_ids = set(result.split('\n')) if result else set()
        assert expected_ids <= actual_ids, f"Missing prompt_ids: {expected_ids - actual_ids}"

    def test_client_prompt_ids_match(self):
        """client_prompt_id values match seeder."""
        expected = get_expected_prompt_analytics_values(self.seeder_data, "client_prompt_id")
        if not expected:
            pytest.skip("No client_prompt_ids in seeder")
        result = execute_query(
            "SELECT DISTINCT client_prompt_id FROM InferenceFact "
            "WHERE client_prompt_id IS NOT NULL AND client_prompt_id != ''"
        )
        actual = set(result.split('\n')) if result else set()
        assert expected <= actual, f"Missing client_prompt_ids: {expected - actual}"

    def test_response_ids_match(self):
        """response_id values match seeder."""
        expected = get_expected_prompt_analytics_values(self.seeder_data, "response_id")
        if not expected:
            pytest.skip("No response_ids in seeder")
        result = execute_query(
            "SELECT DISTINCT response_id FROM InferenceFact "
            "WHERE response_id IS NOT NULL AND response_id != ''"
        )
        actual = set(result.split('\n')) if result else set()
        assert expected <= actual, f"Missing response_ids: {expected - actual}"


@pytest.mark.integration
class TestInferenceFactModelInfo:
    """Test model info fields match seeder."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_all_tables()
        result = seed_otel_traces()
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(1)
        yield

    def test_model_names_match(self):
        """All model_name values match seeder."""
        expected = get_expected_model_values(self.seeder_data, "model_name")
        result = execute_query(
            "SELECT DISTINCT model_name FROM InferenceFact WHERE model_name != ''"
        )
        actual = set(result.split('\n')) if result else set()
        assert expected <= actual, f"Missing model_names: {expected - actual}"

    def test_model_providers_match(self):
        """All model_provider values match seeder."""
        expected = get_expected_model_values(self.seeder_data, "model_provider")
        result = execute_query(
            "SELECT DISTINCT model_provider FROM InferenceFact WHERE model_provider != ''"
        )
        actual = set(result.split('\n')) if result else set()
        assert expected <= actual, f"Missing model_providers: {expected - actual}"

    def test_finish_reason_distribution(self):
        """finish_reason counts match seeder."""
        expected_counts = get_expected_finish_reason_counts(self.seeder_data)
        if not expected_counts:
            pytest.skip("No finish_reasons in seeder")
        result = execute_query(
            "SELECT toString(finish_reason) as fr, count() as cnt FROM InferenceFact "
            "WHERE finish_reason IS NOT NULL GROUP BY fr FORMAT JSONEachRow"
        )
        actual_counts = {}
        if result:
            for line in result.split('\n'):
                if line:
                    row = json.loads(line)
                    actual_counts[row["fr"]] = int(row["cnt"])

        for reason, expected_cnt in expected_counts.items():
            actual_cnt = actual_counts.get(reason, 0)
            assert actual_cnt == expected_cnt, (
                f"finish_reason={reason}: expected={expected_cnt}, actual={actual_cnt}"
            )

    def test_cached_count(self):
        """Count of cached=true matches seeder."""
        expected = get_expected_cached_count(self.seeder_data)
        actual = int(execute_query("SELECT count() FROM InferenceFact WHERE cached = true"))
        assert actual == expected, f"Cached count: expected={expected}, actual={actual}"


# =============================================================================
# ROLLUP AGGREGATE TESTS
# =============================================================================


@pytest.mark.integration
class TestRollup5mAggregates:
    """Test 5-minute rollup aggregates match seeder-derived totals."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_all_tables()
        result = seed_otel_traces()
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(2)  # Wait for cascading MVs
        yield

    def test_request_count_sum(self):
        """Sum of request_count matches seeder row count."""
        expected = get_expected_row_count(self.seeder_data)
        actual = int(execute_query("SELECT sum(request_count) FROM InferenceMetrics5m"))
        assert actual == expected, (
            f"5m request_count sum: expected={expected}, actual={actual}"
        )

    def test_input_tokens_sum(self):
        """Sum of total_input_tokens matches seeder."""
        expected = get_expected_rollup_totals(self.seeder_data)
        actual = int(execute_query("SELECT sum(total_input_tokens) FROM InferenceMetrics5m"))
        assert actual == expected["total_input_tokens"], (
            f"5m input_tokens sum: expected={expected['total_input_tokens']}, actual={actual}"
        )

    def test_output_tokens_sum(self):
        """Sum of total_output_tokens matches seeder."""
        expected = get_expected_rollup_totals(self.seeder_data)
        actual = int(execute_query("SELECT sum(total_output_tokens) FROM InferenceMetrics5m"))
        assert actual == expected["total_output_tokens"], (
            f"5m output_tokens sum: expected={expected['total_output_tokens']}, actual={actual}"
        )

    def test_success_count_sum(self):
        """Sum of success_count matches seeder."""
        expected = get_expected_rollup_totals(self.seeder_data)
        actual = int(execute_query("SELECT sum(success_count) FROM InferenceMetrics5m"))
        assert actual == expected["success_count"], (
            f"5m success_count sum: expected={expected['success_count']}, actual={actual}"
        )

    def test_error_count_sum(self):
        """Sum of error_count matches seeder."""
        expected = get_expected_rollup_totals(self.seeder_data)
        actual = int(execute_query("SELECT sum(error_count) FROM InferenceMetrics5m"))
        assert actual == expected["error_count"], (
            f"5m error_count sum: expected={expected['error_count']}, actual={actual}"
        )


@pytest.mark.integration
class TestRollup5mDimensions:
    """Test dimension UUIDs preserved in 5m rollup."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_all_tables()
        result = seed_otel_traces()
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(2)
        yield

    def test_project_id_preserved(self):
        """All project_id values from seeder present in 5m."""
        expected_ids = get_expected_dimension_values(self.seeder_data, "project_id")
        result = execute_query(
            "SELECT DISTINCT toString(project_id) FROM InferenceMetrics5m "
            "WHERE project_id IS NOT NULL"
        )
        actual_ids = set(result.split('\n')) if result else set()
        assert expected_ids <= actual_ids, (
            f"Missing project_ids in 5m: {expected_ids - actual_ids}"
        )

    def test_endpoint_type_preserved(self):
        """All endpoint_type values preserved in 5m."""
        expected = set(get_expected_endpoint_type_counts(self.seeder_data).keys())
        result = execute_query(
            "SELECT DISTINCT endpoint_type FROM InferenceMetrics5m WHERE endpoint_type != ''"
        )
        actual = set(result.split('\n')) if result else set()
        assert expected <= actual, f"Missing endpoint_types in 5m: {expected - actual}"

    def test_model_name_preserved(self):
        """All model_name values preserved in 5m."""
        expected = get_expected_model_values(self.seeder_data, "model_name")
        result = execute_query(
            "SELECT DISTINCT model_name FROM InferenceMetrics5m WHERE model_name != ''"
        )
        actual = set(result.split('\n')) if result else set()
        assert expected <= actual, f"Missing model_names in 5m: {expected - actual}"


@pytest.mark.integration
class TestRollup5mTimeBuckets:
    """Test 5m time bucket alignment and per-bucket aggregates."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_all_tables()
        result = seed_otel_traces()
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(2)
        yield

    def test_time_bucket_5min_alignment(self):
        """All time_bucket values aligned to 5-minute boundary."""
        result = execute_query("""
            SELECT time_bucket,
                   toStartOfFiveMinutes(time_bucket) as aligned
            FROM InferenceMetrics5m
            WHERE time_bucket != toStartOfFiveMinutes(time_bucket)
        """)
        assert result == "", f"Found misaligned 5m time_buckets: {result}"


@pytest.mark.integration
class TestRollup1hCascade:
    """Test 1-hour rollup cascades correctly from 5m."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_all_tables()
        result = seed_otel_traces()
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(2)
        yield

    def test_request_count_matches_5m(self):
        """1h request_count sum matches 5m sum."""
        sum_5m = int(execute_query("SELECT sum(request_count) FROM InferenceMetrics5m"))
        sum_1h = int(execute_query("SELECT sum(request_count) FROM InferenceMetrics1h"))
        assert sum_1h == sum_5m, f"1h vs 5m request_count: 1h={sum_1h}, 5m={sum_5m}"

    def test_tokens_match_5m(self):
        """1h token sums match 5m sums."""
        tokens_5m = execute_query(
            "SELECT sum(total_input_tokens) as inp, sum(total_output_tokens) as out "
            "FROM InferenceMetrics5m FORMAT JSONEachRow"
        )
        tokens_1h = execute_query(
            "SELECT sum(total_input_tokens) as inp, sum(total_output_tokens) as out "
            "FROM InferenceMetrics1h FORMAT JSONEachRow"
        )
        data_5m = json.loads(tokens_5m) if tokens_5m else {"inp": 0, "out": 0}
        data_1h = json.loads(tokens_1h) if tokens_1h else {"inp": 0, "out": 0}
        assert int(data_1h["inp"]) == int(data_5m["inp"]), (
            f"1h vs 5m input_tokens: 1h={data_1h['inp']}, 5m={data_5m['inp']}"
        )
        assert int(data_1h["out"]) == int(data_5m["out"]), (
            f"1h vs 5m output_tokens: 1h={data_1h['out']}, 5m={data_5m['out']}"
        )

    def test_time_bucket_hourly_alignment(self):
        """All 1h time_bucket values aligned to hour boundary."""
        result = execute_query("""
            SELECT time_bucket,
                   toStartOfHour(time_bucket) as aligned
            FROM InferenceMetrics1h
            WHERE time_bucket != toStartOfHour(time_bucket)
        """)
        assert result == "", f"Found misaligned 1h time_buckets: {result}"


@pytest.mark.integration
class TestRollup1dCascade:
    """Test 1-day rollup cascades correctly from 1h."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_all_tables()
        result = seed_otel_traces()
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(2)
        yield

    def test_request_count_matches_1h(self):
        """1d request_count sum matches 1h sum."""
        sum_1h = int(execute_query("SELECT sum(request_count) FROM InferenceMetrics1h"))
        sum_1d = int(execute_query("SELECT sum(request_count) FROM InferenceMetrics1d"))
        assert sum_1d == sum_1h, f"1d vs 1h request_count: 1d={sum_1d}, 1h={sum_1h}"

    def test_tokens_match_1h(self):
        """1d token sums match 1h sums."""
        tokens_1h = execute_query(
            "SELECT sum(total_input_tokens) as inp, sum(total_output_tokens) as out "
            "FROM InferenceMetrics1h FORMAT JSONEachRow"
        )
        tokens_1d = execute_query(
            "SELECT sum(total_input_tokens) as inp, sum(total_output_tokens) as out "
            "FROM InferenceMetrics1d FORMAT JSONEachRow"
        )
        data_1h = json.loads(tokens_1h) if tokens_1h else {"inp": 0, "out": 0}
        data_1d = json.loads(tokens_1d) if tokens_1d else {"inp": 0, "out": 0}
        assert int(data_1d["inp"]) == int(data_1h["inp"]), (
            f"1d vs 1h input_tokens: 1d={data_1d['inp']}, 1h={data_1h['inp']}"
        )
        assert int(data_1d["out"]) == int(data_1h["out"]), (
            f"1d vs 1h output_tokens: 1d={data_1d['out']}, 1h={data_1h['out']}"
        )

    def test_time_bucket_daily_alignment(self):
        """All 1d time_bucket values aligned to day boundary."""
        result = execute_query("""
            SELECT time_bucket,
                   toStartOfDay(time_bucket) as aligned
            FROM InferenceMetrics1d
            WHERE time_bucket != toStartOfDay(time_bucket)
        """)
        assert result == "", f"Found misaligned 1d time_buckets: {result}"


# =============================================================================
# PER-SCENARIO VALIDATION TESTS (Secondary - specific field validation)
# =============================================================================


@pytest.mark.integration
class TestInferenceFactFromChatCompletion:
    """Test MV transformation for /v1/chat/completions."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Clear DB and seed chat data before each test."""
        clear_all_tables()
        result = seed_otel_traces(["chat_success"])
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(0.5)  # Wait for MV
        yield

    def test_inference_fact_row_created(self):
        """Verify InferenceFact row exists for chat completion."""
        expected = get_expected_inference_fact(self.seeder_data, "chat_success")
        rows = query_inference_fact_by_trace(expected["trace_id"])
        assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"

    def test_core_identifiers(self):
        """Verify core identifiers match derived ground truth."""
        expected = get_expected_inference_fact(self.seeder_data, "chat_success")
        actual = query_inference_fact(expected["inference_id"])
        assert actual is not None, "InferenceFact row not found"

        for col in ["trace_id", "inference_id", "project_id", "endpoint_id"]:
            expected_val = expected[col]
            actual_val = actual.get(col)
            assert compare_values(expected_val, actual_val, col), (
                f"{col}: expected={expected_val!r}, actual={actual_val!r}"
            )

    def test_model_inference_fields(self):
        """Verify model inference fields from handler span."""
        expected = get_expected_inference_fact(self.seeder_data, "chat_success")
        actual = query_inference_fact(expected["inference_id"])

        model_fields = [
            "model_provider", "endpoint_type", "input_tokens",
            "output_tokens", "response_time_ms", "cached", "finish_reason"
        ]
        mismatches = []
        for col in model_fields:
            if col in SKIP_COLUMNS:
                continue
            expected_val = expected.get(col)
            actual_val = actual.get(col)
            if not compare_values(expected_val, actual_val, col):
                mismatches.append(f"{col}: expected={expected_val!r}, actual={actual_val!r}")

        assert not mismatches, f"Model field mismatches:\n" + "\n".join(mismatches)

    def test_gateway_analytics_fields(self):
        """Verify gateway analytics fields from LEFT JOIN."""
        expected = get_expected_inference_fact(self.seeder_data, "chat_success")
        actual = query_inference_fact(expected["inference_id"])

        gateway_fields = [
            "method", "path", "device_type", "browser_name",
            "gateway_processing_ms", "total_duration_ms", "status_code"
        ]
        mismatches = []
        for col in gateway_fields:
            expected_val = expected.get(col)
            actual_val = actual.get(col)
            if not compare_values(expected_val, actual_val, col):
                mismatches.append(f"{col}: expected={expected_val!r}, actual={actual_val!r}")

        assert not mismatches, f"Gateway field mismatches:\n" + "\n".join(mismatches)

    def test_prompt_analytics_null_for_chat(self):
        """Verify prompt analytics fields are NULL for chat (not /v1/responses)."""
        expected = get_expected_inference_fact(self.seeder_data, "chat_success")
        actual = query_inference_fact(expected["inference_id"])

        prompt_fields = ["prompt_id", "client_prompt_id", "prompt_version", "response_id"]
        for col in prompt_fields:
            expected_val = expected.get(col)
            actual_val = actual.get(col)
            # Both should be None/empty for chat endpoint
            assert compare_values(expected_val, actual_val, col), (
                f"{col}: expected={expected_val!r}, actual={actual_val!r}"
            )


@pytest.mark.integration
class TestInferenceFactFromResponseEndpoint:
    """Test MV transformation for /v1/responses with prompt analytics."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Clear DB and seed response data before each test."""
        clear_all_tables()
        result = seed_otel_traces(["response_prompt"])
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(0.5)
        yield

    def test_inference_fact_row_created(self):
        """Verify InferenceFact row exists for /v1/responses."""
        expected = get_expected_inference_fact(self.seeder_data, "response_prompt")
        rows = query_inference_fact_by_trace(expected["trace_id"])
        assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"

    def test_prompt_analytics_populated(self):
        """Verify prompt analytics fields are populated (derived from seeder)."""
        expected = get_expected_inference_fact(self.seeder_data, "response_prompt")
        actual = query_inference_fact(expected["inference_id"])
        assert actual is not None, "InferenceFact row not found"

        prompt_fields = [
            "prompt_id", "client_prompt_id", "prompt_version",
            "response_id", "response_status"
        ]
        mismatches = []
        for col in prompt_fields:
            expected_val = expected.get(col)
            actual_val = actual.get(col)
            if not compare_values(expected_val, actual_val, col):
                mismatches.append(f"{col}: expected={expected_val!r}, actual={actual_val!r}")

        assert not mismatches, f"Prompt analytics mismatches:\n" + "\n".join(mismatches)

    def test_model_provider_is_budprompt(self):
        """Verify model_provider is 'budprompt' for /v1/responses."""
        expected = get_expected_inference_fact(self.seeder_data, "response_prompt")
        actual = query_inference_fact(expected["inference_id"])
        assert actual.get("model_provider") == "budprompt", (
            f"Expected model_provider='budprompt', got {actual.get('model_provider')!r}"
        )

    def test_endpoint_type_is_response(self):
        """Verify endpoint_type is 'response' for /v1/responses."""
        expected = get_expected_inference_fact(self.seeder_data, "response_prompt")
        actual = query_inference_fact(expected["inference_id"])
        assert actual.get("endpoint_type") == "response", (
            f"Expected endpoint_type='response', got {actual.get('endpoint_type')!r}"
        )


@pytest.mark.integration
class TestInferenceFactErrorCase:
    """Test MV transformation for error responses."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_all_tables()
        result = seed_otel_traces(["chat_error"])
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(0.5)
        yield

    def test_is_success_false(self):
        """Verify is_success=false for error response."""
        expected = get_expected_inference_fact(self.seeder_data, "chat_error")
        actual = query_inference_fact(expected["inference_id"])

        assert actual.get("is_success") is False, (
            f"Expected is_success=false, got {actual.get('is_success')}"
        )

    def test_error_fields_populated(self):
        """Verify error_code, error_message, error_type from seeder."""
        expected = get_expected_inference_fact(self.seeder_data, "chat_error")
        actual = query_inference_fact(expected["inference_id"])

        for col in ["error_code", "error_message", "error_type"]:
            expected_val = expected.get(col)
            actual_val = actual.get(col)
            assert compare_values(expected_val, actual_val, col), (
                f"{col}: expected={expected_val!r}, actual={actual_val!r}"
            )


@pytest.mark.integration
class TestInferenceFactBlockedRequest:
    """Test MV transformation for blocked requests."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_all_tables()
        result = seed_otel_traces(["blocked_request"])
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(0.5)
        yield

    def test_is_blocked_true(self):
        """Verify is_blocked=true for blocked request."""
        expected = get_expected_inference_fact(self.seeder_data, "blocked_request")
        rows = query_inference_fact_by_trace(expected["trace_id"])
        assert len(rows) > 0, "No InferenceFact rows found"
        actual = rows[0]

        assert actual.get("is_blocked") is True, (
            f"Expected is_blocked=true, got {actual.get('is_blocked')}"
        )

    def test_blocking_event_fields(self):
        """Verify blocking event fields from gateway span."""
        expected = get_expected_inference_fact(self.seeder_data, "blocked_request")
        rows = query_inference_fact_by_trace(expected["trace_id"])
        actual = rows[0]

        blocking_fields = ["block_reason", "rule_type", "rule_name", "action_taken"]
        populated_fields = []
        for col in blocking_fields:
            expected_val = expected.get(col)
            actual_val = actual.get(col)
            if expected_val and compare_values(expected_val, actual_val, col):
                populated_fields.append(col)

        # At least one blocking field should be populated
        assert len(populated_fields) > 0, "No blocking fields populated"


@pytest.mark.integration
class TestInferenceFactEmbeddingEndpoint:
    """Test MV transformation for embedding endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_all_tables()
        result = seed_otel_traces(["embedding"])
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(0.5)
        yield

    def test_embedding_fields_populated(self):
        """Verify embedding-specific fields from handler span."""
        expected = get_expected_inference_fact(self.seeder_data, "embedding")
        actual = query_inference_fact(expected["inference_id"])

        embedding_fields = ["embedding_input_count", "embedding_dimensions", "embedding_encoding_format"]
        for col in embedding_fields:
            expected_val = expected.get(col)
            actual_val = actual.get(col)
            assert compare_values(expected_val, actual_val, col), (
                f"{col}: expected={expected_val!r}, actual={actual_val!r}"
            )

    def test_endpoint_type_is_embedding(self):
        """Verify endpoint_type is 'embedding'."""
        expected = get_expected_inference_fact(self.seeder_data, "embedding")
        actual = query_inference_fact(expected["inference_id"])

        assert actual.get("endpoint_type") == "embedding", (
            f"Expected 'embedding', got {actual.get('endpoint_type')!r}"
        )


@pytest.mark.integration
class TestInferenceFactMissingHandler:
    """Test MV transformation when handler span is missing (LEFT JOIN behavior)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_all_tables()
        result = seed_otel_traces(["missing_handler"])
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(0.5)
        yield

    def test_row_created_from_gateway_only(self):
        """Verify InferenceFact row exists even without handler span."""
        expected = get_expected_inference_fact(self.seeder_data, "missing_handler")
        rows = query_inference_fact_by_trace(expected["trace_id"])

        assert len(rows) == 1, f"Expected 1 row from gateway-only, got {len(rows)}"

    def test_gateway_fields_populated(self):
        """Verify gateway fields are populated even without handler."""
        expected = get_expected_inference_fact(self.seeder_data, "missing_handler")
        rows = query_inference_fact_by_trace(expected["trace_id"])
        actual = rows[0]

        gateway_fields = ["method", "path", "country_code", "device_type"]
        for col in gateway_fields:
            expected_val = expected.get(col)
            actual_val = actual.get(col)
            # Should have gateway data
            if expected_val:
                assert compare_values(expected_val, actual_val, col), (
                    f"{col}: expected={expected_val!r}, actual={actual_val!r}"
                )

    def test_handler_fields_null(self):
        """Verify handler-specific fields are NULL when handler missing."""
        expected = get_expected_inference_fact(self.seeder_data, "missing_handler")
        rows = query_inference_fact_by_trace(expected["trace_id"])
        actual = rows[0]

        handler_fields = ["input_tokens", "output_tokens", "response_time_ms"]
        for col in handler_fields:
            actual_val = actual.get(col)
            # Should be NULL (or default) when handler missing
            assert actual_val is None or actual_val == "" or actual_val == 0, (
                f"{col} should be NULL when handler missing, got {actual_val!r}"
            )


@pytest.mark.integration
class TestSpanIdBugFix:
    """Test span_id is correctly populated (not empty string)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        clear_all_tables()
        result = seed_otel_traces()
        assert result.get("success"), f"Seeding failed: {result}"
        time.sleep(0.5)
        yield

    def test_span_id_not_empty(self):
        """Verify span_id is never empty string."""
        result = execute_query("""
            SELECT trace_id, span_id, toString(inference_id) as inference_id
            FROM InferenceFact
            WHERE span_id = ''
            FORMAT JSONEachRow
        """)

        if result:
            rows = [json.loads(line) for line in result.split('\n') if line]
            assert len(rows) == 0, (
                f"Found {len(rows)} rows with empty span_id (COALESCE bug): {rows}"
            )


@pytest.mark.integration
class TestRollupPromptIdPreserved:
    """Test prompt_id is preserved in rollup tables."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Clear DB and seed all data."""
        clear_all_tables()
        result = seed_otel_traces()
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(2)  # Wait for all cascading MVs
        yield

    def test_prompt_id_in_5m(self):
        """Verify prompt_id from seeder is preserved in 5m rollup."""
        expected_prompt_ids = set()
        for scenario_key in self.seeder_data:
            expected = get_expected_inference_fact(self.seeder_data, scenario_key)
            if expected.get("prompt_id"):
                expected_prompt_ids.add(expected["prompt_id"])

        if not expected_prompt_ids:
            pytest.skip("No prompt_ids in seeder data")

        result = execute_query("""
            SELECT DISTINCT toString(prompt_id) as prompt_id
            FROM InferenceMetrics5m
            WHERE prompt_id IS NOT NULL AND prompt_id != ''
        """)

        actual_prompt_ids = set()
        if result:
            actual_prompt_ids = set(result.split('\n'))

        assert expected_prompt_ids <= actual_prompt_ids, (
            f"Missing prompt_ids in rollup: {expected_prompt_ids - actual_prompt_ids}"
        )

    def test_prompt_id_in_1h(self):
        """Verify prompt_id preserved in 1h rollup."""
        expected_prompt_ids = set()
        for scenario_key in self.seeder_data:
            expected = get_expected_inference_fact(self.seeder_data, scenario_key)
            if expected.get("prompt_id"):
                expected_prompt_ids.add(expected["prompt_id"])

        if not expected_prompt_ids:
            pytest.skip("No prompt_ids in seeder data")

        result = execute_query("""
            SELECT DISTINCT toString(prompt_id) as prompt_id
            FROM InferenceMetrics1h
            WHERE prompt_id IS NOT NULL AND prompt_id != ''
        """)

        actual_prompt_ids = set()
        if result:
            actual_prompt_ids = set(result.split('\n'))

        assert expected_prompt_ids <= actual_prompt_ids, (
            f"Missing prompt_ids in 1h rollup: {expected_prompt_ids - actual_prompt_ids}"
        )

    def test_prompt_id_in_1d(self):
        """Verify prompt_id preserved in 1d rollup."""
        expected_prompt_ids = set()
        for scenario_key in self.seeder_data:
            expected = get_expected_inference_fact(self.seeder_data, scenario_key)
            if expected.get("prompt_id"):
                expected_prompt_ids.add(expected["prompt_id"])

        if not expected_prompt_ids:
            pytest.skip("No prompt_ids in seeder data")

        result = execute_query("""
            SELECT DISTINCT toString(prompt_id) as prompt_id
            FROM InferenceMetrics1d
            WHERE prompt_id IS NOT NULL AND prompt_id != ''
        """)

        actual_prompt_ids = set()
        if result:
            actual_prompt_ids = set(result.split('\n'))

        assert expected_prompt_ids <= actual_prompt_ids, (
            f"Missing prompt_ids in 1d rollup: {expected_prompt_ids - actual_prompt_ids}"
        )


@pytest.mark.integration
class TestCascadeTotalsMatch:
    """Test totals match expected from seeder across all rollup levels."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Clear DB and seed all data."""
        clear_all_tables()
        result = seed_otel_traces()
        assert result.get("success"), f"Seeding failed: {result}"
        self.seeder_data = load_test_data()
        time.sleep(2)  # Wait for all cascading MVs
        yield

    def test_cascade_totals_match_seeder(self):
        """Verify totals match expected from seeder across all rollup levels."""
        expected_totals = get_expected_rollup_totals(self.seeder_data)

        # Query totals from each level
        for table in ["InferenceMetrics5m", "InferenceMetrics1h", "InferenceMetrics1d"]:
            result = execute_query(f"""
                SELECT
                    sum(request_count) as request_count,
                    sum(total_input_tokens) as input_tokens,
                    sum(total_output_tokens) as output_tokens
                FROM {table}
                FORMAT JSONEachRow
            """)
            actual = json.loads(result) if result else {}

            assert int(actual.get("request_count", 0)) == expected_totals["request_count"], (
                f"request_count mismatch in {table}: "
                f"expected={expected_totals['request_count']}, actual={actual.get('request_count')}"
            )
            assert int(actual.get("input_tokens", 0)) == expected_totals["total_input_tokens"], (
                f"input_tokens mismatch in {table}: "
                f"expected={expected_totals['total_input_tokens']}, actual={actual.get('input_tokens')}"
            )
