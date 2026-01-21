"""Integration tests for OTel traces to InferenceFact pipeline.

Tests verify that the MaterializedView correctly transforms OTel trace spans
(inference_handler_observability and gateway_analytics) into InferenceFact rows.

Uses explicit ground truth values to validate MV transformations.
"""

import json
import subprocess

import pytest

DATABASE = "default_v4"
CONTAINER = "otel-clickhouse"

# =============================================================================
# EXPLICIT GROUND TRUTH VALUES
# =============================================================================
# These values represent exactly what the MV SHOULD produce from the OTel spans.
# If the MV logic is incorrect, these tests will fail.

EXPECTED_DATA_1 = {
    # Core identifiers (from model_inference_details.*)
    "trace_id": "eabbcee5ecd7bde08b51580b32136a14",
    "inference_id": "019b971a-2ac3-7143-8bad-d109ed8eb867",
    "project_id": "019787c1-3de1-7b50-969b-e0a58514b6a1",
    "endpoint_id": "019787c1-3de1-7b50-969b-e0a58514b6a4",
    "model_id": "019787c1-3de1-7b50-969b-e0a58514b6a2",
    "api_key_id": None,
    "api_key_project_id": None,
    "user_id": None,
    # Status
    "is_success": True,
    "status_code": None,
    "cost": None,
    "request_ip": None,
    "response_analysis": None,
    # Error fields (not set in success case)
    "error_code": None,
    "error_message": None,
    "error_type": None,
    # Model inference (from model_inference.*)
    "model_inference_id": "019b971a-331f-74a2-8771-48264bf581bd",
    "model_name": "019787c1-3de1-7b50-969b-e0a58514b6a4",
    "model_provider": "vllm",
    "endpoint_type": "chat",
    "input_tokens": 14,
    "output_tokens": 21,
    "response_time_ms": 2125,
    "ttft_ms": 450,
    "cached": True,
    "finish_reason": "stop",
    "model_inference_timestamp": 1767766635,
    "system_prompt": None,
    "guardrail_scan_summary": None,
    # Chat inference (from chat_inference.*)
    "chat_inference_id": "019b971a-2ac3-7143-8bad-d109ed8eb867",
    "episode_id": "019b971a-2ac3-7143-8bad-d11b9f3deda9",
    "function_name": "tensorzero::default",
    "variant_name": "019787c1-3de1-7b50-969b-e0a58514b6a4",
    "processing_time_ms": 2141,
    "tags": "{}",
    "inference_params": '{"chat_completion":{}}',
    "extra_body": "[]",
    "tool_params": None,
    # Gateway analytics (from gateway_analytics.* via LEFT JOIN)
    "device_type": "desktop",
    "browser_name": "PostmanRuntime",
    "browser_version": "7.51",
    "os_name": "Other",
    "os_version": None,
    "is_bot": False,
    "method": "POST",
    "path": "/v1/chat/completions",
    "protocol_version": "HTTP/1.1",
    "user_agent": "PostmanRuntime/7.51.0",
    "gateway_processing_ms": 211,
    "total_duration_ms": 2336,
    "is_blocked": False,
    "block_reason": None,
    "block_rule_id": None,
    "client_ip": None,  # "unknown" becomes NULL in ClickHouse IPv4
    "proxy_chain": None,
    "query_params": None,
    "body_size": None,
    "response_size": None,
    "request_headers": '{"content-type":"application/json","accept":"*/*"}',
    "response_headers": '{"content-type":"application/json"}',
    "gateway_tags": "{}",
    # Geo fields (not present in data_1)
    "country_code": None,
    "country_name": None,
    "region": None,
    "city": None,
    "latitude": None,
    "longitude": None,
    "timezone": None,
    "asn": None,
    "isp": None,
    "model_version": None,
    "routing_decision": None,
}

EXPECTED_DATA_4 = {
    # Core identifiers
    "trace_id": "95760d615a844a14df6780a8ccddb54c",
    "inference_id": "019b9786-a69c-73b1-a868-f507b0aa546f",
    "project_id": "019787c1-3de1-7b50-969b-e0a58514b6a1",
    "endpoint_id": "019787c1-3de1-7b50-969b-e0a58514b6a4",
    "model_id": "019787c1-3de1-7b50-969b-e0a58514b6a2",
    "api_key_id": None,
    "api_key_project_id": None,
    "user_id": None,
    # Status (error case)
    "is_success": False,
    "status_code": 502,
    "cost": None,
    "request_ip": None,
    "response_analysis": None,
    # Error fields (populated for error case)
    "error_code": "AllVariantsFailed",
    "error_message": "All variants failed with 1 error(s)",
    "error_type": "AllVariantsFailed",
    # Model inference fields should be NULL for error case
    "model_inference_id": None,
    "model_name": "",  # Empty string from MV (no nullIf)
    "model_provider": "",  # Empty string from MV
    "endpoint_type": "chat",  # Default value from MV
    "input_tokens": None,
    "output_tokens": None,
    "response_time_ms": None,
    "ttft_ms": None,
    "cached": False,  # Default to false
    "finish_reason": None,
    "model_inference_timestamp": None,
    "system_prompt": None,
    "guardrail_scan_summary": None,
    # Chat inference fields should be NULL for error case
    "chat_inference_id": None,
    "episode_id": None,
    "function_name": None,
    "variant_name": None,
    "processing_time_ms": None,
    "tags": None,
    "inference_params": None,
    "extra_body": None,
    "tool_params": None,
    # Gateway analytics (from LEFT JOIN)
    "device_type": "desktop",
    "browser_name": "PostmanRuntime",
    "browser_version": "7.51",
    "os_name": "Other",
    "os_version": None,
    "is_bot": False,
    "method": "POST",
    "path": "/v1/chat/completions",
    "protocol_version": "HTTP/1.1",
    "user_agent": "PostmanRuntime/7.51.0",
    "gateway_processing_ms": 0,
    "total_duration_ms": 1221,
    "is_blocked": False,
    "block_reason": None,
    "block_rule_id": None,
    "client_ip": None,
    "proxy_chain": None,
    "query_params": None,
    "body_size": None,
    "response_size": None,
    "request_headers": '{"content-type":"application/json","accept":"*/*"}',
    "response_headers": '{"content-type":"application/json"}',
    "gateway_tags": "{}",
    # Geo fields (not present in data_4)
    "country_code": None,
    "country_name": None,
    "region": None,
    "city": None,
    "latitude": None,
    "longitude": None,
    "timezone": None,
    "asn": None,
    "isp": None,
    "model_version": None,
    "routing_decision": None,
}

EXPECTED_DATA_6 = {
    # Core identifiers
    "trace_id": "eabbcee5ecd7bde08b51580b32136a17",
    "inference_id": "019b971a-2ac3-7143-8bad-d109ed8eb878",
    "project_id": "019787c1-3de1-7b50-969b-e0a58514b6a1",
    "endpoint_id": "019787c1-3de1-7b50-969b-e0a58514b6a4",
    "model_id": "019787c1-3de1-7b50-969b-e0a58514b6a2",
    "api_key_id": "019b971a-4a01-7000-a001-a10000000001",
    "api_key_project_id": "019b971a-4a01-7000-a001-a10000000003",
    "user_id": "019b971a-4a01-7000-a001-a10000000002",
    # Status
    "is_success": True,
    "status_code": 200,
    "cost": 0.00125,
    "request_ip": "192.168.1.100",
    "response_analysis": '{"sentiment":"positive","confidence":0.95}',
    # Error fields (not set in success case)
    "error_code": None,
    "error_message": None,
    "error_type": None,
    # Model inference
    "model_inference_id": "019b971a-331f-74a2-8771-48264bf581ce",
    "model_name": "019787c1-3de1-7b50-969b-e0a58514b6a4",
    "model_provider": "vllm",
    "endpoint_type": "chat",
    "input_tokens": 24,
    "output_tokens": 31,
    "response_time_ms": 1125,
    "ttft_ms": 250,
    "cached": True,
    "finish_reason": "stop",
    "model_inference_timestamp": 1767781035,
    "system_prompt": "You are a helpful assistant that summarizes text concisely.",
    "guardrail_scan_summary": '{"passed":true,"scans":[]}',
    # Chat inference
    "chat_inference_id": "019b971a-2ac3-7143-8bad-d109ed8eb878",
    "episode_id": "019b971a-2ac3-7143-8bad-d11b9f3dedb0",
    "function_name": "tensorzero::default",
    "variant_name": "019787c1-3de1-7b50-969b-e0a58514b6a4",
    "processing_time_ms": 1141,
    "tags": "{}",
    "inference_params": '{"chat_completion":{}}',
    "extra_body": "[]",
    "tool_params": "{}",
    # Gateway analytics (full data with geo)
    "device_type": "desktop",
    "browser_name": "PostmanRuntime",
    "browser_version": "7.51",
    "os_name": "Other",
    "os_version": None,
    "is_bot": False,
    "method": "POST",
    "path": "/v1/chat/completions",
    "protocol_version": "HTTP/1.1",
    "user_agent": "PostmanRuntime/7.51.0",
    "gateway_processing_ms": 211,
    "total_duration_ms": 2336,
    "is_blocked": False,
    "block_reason": None,
    "block_rule_id": None,
    "client_ip": "192.168.1.100",
    "proxy_chain": None,
    "query_params": None,
    "body_size": 256,
    "response_size": 512,
    "request_headers": '{"content-type":"application/json","accept":"*/*"}',
    "response_headers": '{"content-type":"application/json"}',
    "gateway_tags": "{}",
    # Geo fields (present in data_6)
    "country_code": "US",
    "country_name": "United States",
    "region": "California",
    "city": "Mountain View",
    "latitude": 37.4056,
    "longitude": -122.0775,
    "timezone": "America/Los_Angeles",
    "asn": 15169,
    "isp": "Google LLC",
    "model_version": "gpt-4.1-2025-04-14",
    "routing_decision": "primary",
}

# Columns to skip in comparison (generated by MV or system)
SKIP_COLUMNS = {
    "id",  # Generated UUID
    "span_id",  # Not critical for validation
    "timestamp",  # Generated from span timestamp
    "date",  # Materialized from timestamp
    "hour",  # Materialized from timestamp
    "request_arrival_time",  # DateTime format comparison is complex
    "request_forward_time",  # DateTime format comparison is complex
    "request_timestamp",  # DateTime format comparison is complex
    "response_timestamp",  # DateTime format comparison is complex
    "blocked_at",  # DateTime format comparison is complex
    # Content fields - too long to compare, verified separately
    "input_messages",
    "output",
    "raw_request",
    "raw_response",
    "gateway_request",
    "gateway_response",
    "chat_input",
    "chat_output",
}


def execute_query(query: str) -> str:
    """Execute ClickHouse query via docker."""
    cmd = ["docker", "exec", CONTAINER, "clickhouse-client", "--query", query]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Query failed: {result.stderr}")
    return result.stdout.strip()


def query_inference_fact(inference_id: str) -> dict:
    """Query InferenceFact for a specific inference_id and return as dict."""
    query = f"""
    SELECT *
    FROM {DATABASE}.InferenceFact
    WHERE inference_id = '{inference_id}'
    FORMAT JSONEachRow
    """
    result = execute_query(query)
    if not result:
        return {}
    return json.loads(result)


def compare_values(expected_val, actual_val, column: str) -> bool:
    """Compare expected ground truth with actual InferenceFact value."""
    # Handle None comparisons
    if expected_val is None:
        # ClickHouse returns various representations of NULL
        return actual_val is None or actual_val == "" or actual_val == "0.0.0.0"

    if actual_val is None or actual_val == "":
        return expected_val is None or expected_val == ""

    # Type-specific comparisons based on expected type
    if isinstance(expected_val, bool):
        return expected_val == actual_val
    elif isinstance(expected_val, int):
        try:
            return expected_val == int(actual_val)
        except (ValueError, TypeError):
            return False
    elif isinstance(expected_val, float):
        try:
            return abs(expected_val - float(actual_val)) < 0.0001
        except (ValueError, TypeError):
            return False
    else:
        # String comparison
        return str(expected_val) == str(actual_val)


def seed_data(data_keys: list[str]) -> dict:
    """Seed specific data keys to ClickHouse."""
    from tests.observability.seed_otel_traces import seed_otel_traces

    return seed_otel_traces(data_keys=data_keys, database=DATABASE, container=CONTAINER)


def clear_tables():
    """Clear otel_traces and InferenceFact tables."""
    for table in ["otel_traces", "InferenceFact"]:
        try:
            execute_query(f"TRUNCATE TABLE {DATABASE}.{table}")
        except RuntimeError:
            pass  # Table might not exist


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Clear tables before each test."""
    clear_tables()
    yield


class TestInferenceFactData1:
    """Test data_1: Basic success case with chat inference."""

    @pytest.mark.integration
    def test_data_1_populates_inference_fact(self):
        """Verify data_1 seeds correctly and InferenceFact has expected values."""
        result = seed_data(["data_1"])
        assert result.get("success"), f"Seed failed: {result}"

        actual = query_inference_fact(EXPECTED_DATA_1["inference_id"])
        assert actual, f"No InferenceFact row found for inference_id={EXPECTED_DATA_1['inference_id']}"

        mismatches = []
        for col, expected_val in EXPECTED_DATA_1.items():
            if col in SKIP_COLUMNS:
                continue
            actual_val = actual.get(col)
            if not compare_values(expected_val, actual_val, col):
                mismatches.append(f"{col}: expected={expected_val!r}, actual={actual_val!r}")

        assert not mismatches, "Mismatches in data_1:\n" + "\n".join(mismatches)

    @pytest.mark.integration
    def test_data_1_trace_id_matches(self):
        """Verify trace_id is correctly extracted from OTel span."""
        result = seed_data(["data_1"])
        assert result.get("success")

        actual = query_inference_fact(EXPECTED_DATA_1["inference_id"])
        assert actual["trace_id"] == EXPECTED_DATA_1["trace_id"]

    @pytest.mark.integration
    def test_data_1_model_inference_fields(self):
        """Verify model inference fields are correctly transformed."""
        result = seed_data(["data_1"])
        assert result.get("success")

        actual = query_inference_fact(EXPECTED_DATA_1["inference_id"])

        # Verify column renames
        assert actual["model_provider"] == "vllm"  # model_inference.model_provider_name -> model_provider
        assert actual["model_inference_id"] == "019b971a-331f-74a2-8771-48264bf581bd"  # model_inference.id

        # Verify type conversions
        assert actual["input_tokens"] == 14
        assert actual["output_tokens"] == 21
        assert actual["cached"] is True
        assert actual["finish_reason"] == "stop"

    @pytest.mark.integration
    def test_data_1_gateway_join(self):
        """Verify gateway analytics data is joined via LEFT JOIN."""
        result = seed_data(["data_1"])
        assert result.get("success")

        actual = query_inference_fact(EXPECTED_DATA_1["inference_id"])

        # Verify gateway fields populated from gateway_analytics span
        assert actual["device_type"] == "desktop"
        assert actual["method"] == "POST"
        assert actual["path"] == "/v1/chat/completions"
        assert actual["user_agent"] == "PostmanRuntime/7.51.0"
        assert actual["gateway_processing_ms"] == 211
        assert actual["total_duration_ms"] == 2336


class TestInferenceFactData4:
    """Test data_4: Error case (AllVariantsFailed)."""

    @pytest.mark.integration
    def test_data_4_populates_inference_fact(self):
        """Verify data_4 error case seeds correctly."""
        result = seed_data(["data_4"])
        assert result.get("success"), f"Seed failed: {result}"

        actual = query_inference_fact(EXPECTED_DATA_4["inference_id"])
        assert actual, f"No InferenceFact row found for inference_id={EXPECTED_DATA_4['inference_id']}"

        mismatches = []
        for col, expected_val in EXPECTED_DATA_4.items():
            if col in SKIP_COLUMNS:
                continue
            actual_val = actual.get(col)
            if not compare_values(expected_val, actual_val, col):
                mismatches.append(f"{col}: expected={expected_val!r}, actual={actual_val!r}")

        assert not mismatches, "Mismatches in data_4:\n" + "\n".join(mismatches)

    @pytest.mark.integration
    def test_data_4_error_fields(self):
        """Verify error fields are correctly populated."""
        result = seed_data(["data_4"])
        assert result.get("success")

        actual = query_inference_fact(EXPECTED_DATA_4["inference_id"])

        assert actual["is_success"] is False
        assert actual["status_code"] == 502
        assert actual["error_code"] == "AllVariantsFailed"
        assert actual["error_message"] == "All variants failed with 1 error(s)"
        assert actual["error_type"] == "AllVariantsFailed"

    @pytest.mark.integration
    def test_data_4_model_inference_null(self):
        """Verify model inference fields are NULL for error case."""
        result = seed_data(["data_4"])
        assert result.get("success")

        actual = query_inference_fact(EXPECTED_DATA_4["inference_id"])

        # Model inference fields should be NULL (no successful inference)
        assert actual["model_inference_id"] is None
        assert actual["input_tokens"] is None
        assert actual["output_tokens"] is None


class TestInferenceFactData6:
    """Test data_6: Full data case with geo and all fields."""

    @pytest.mark.integration
    def test_data_6_populates_inference_fact(self):
        """Verify data_6 with full data seeds correctly."""
        result = seed_data(["data_6"])
        assert result.get("success"), f"Seed failed: {result}"

        actual = query_inference_fact(EXPECTED_DATA_6["inference_id"])
        assert actual, f"No InferenceFact row found for inference_id={EXPECTED_DATA_6['inference_id']}"

        mismatches = []
        for col, expected_val in EXPECTED_DATA_6.items():
            if col in SKIP_COLUMNS:
                continue
            actual_val = actual.get(col)
            if not compare_values(expected_val, actual_val, col):
                mismatches.append(f"{col}: expected={expected_val!r}, actual={actual_val!r}")

        assert not mismatches, "Mismatches in data_6:\n" + "\n".join(mismatches)

    @pytest.mark.integration
    def test_data_6_geographic_fields(self):
        """Verify geographic fields from gateway_analytics."""
        result = seed_data(["data_6"])
        assert result.get("success")

        actual = query_inference_fact(EXPECTED_DATA_6["inference_id"])

        assert actual["country_code"] == "US"
        assert actual["country_name"] == "United States"
        assert actual["region"] == "California"
        assert actual["city"] == "Mountain View"
        assert abs(float(actual["latitude"]) - 37.4056) < 0.001
        assert abs(float(actual["longitude"]) - (-122.0775)) < 0.001
        assert actual["timezone"] == "America/Los_Angeles"
        assert actual["asn"] == 15169
        assert actual["isp"] == "Google LLC"

    @pytest.mark.integration
    def test_data_6_cost_and_metadata(self):
        """Verify cost, api_key, user fields."""
        result = seed_data(["data_6"])
        assert result.get("success")

        actual = query_inference_fact(EXPECTED_DATA_6["inference_id"])

        assert abs(float(actual["cost"]) - 0.00125) < 0.00001
        assert actual["api_key_id"] == "019b971a-4a01-7000-a001-a10000000001"
        assert actual["api_key_project_id"] == "019b971a-4a01-7000-a001-a10000000003"
        assert actual["user_id"] == "019b971a-4a01-7000-a001-a10000000002"
        assert actual["routing_decision"] == "primary"
        assert actual["model_version"] == "gpt-4.1-2025-04-14"

    @pytest.mark.integration
    def test_data_6_system_prompt(self):
        """Verify system_prompt is correctly extracted."""
        result = seed_data(["data_6"])
        assert result.get("success")

        actual = query_inference_fact(EXPECTED_DATA_6["inference_id"])

        assert actual["system_prompt"] == "You are a helpful assistant that summarizes text concisely."
        assert actual["guardrail_scan_summary"] == '{"passed":true,"scans":[]}'


@pytest.mark.integration
@pytest.mark.parametrize(
    "data_key,expected",
    [
        ("data_1", EXPECTED_DATA_1),
        ("data_4", EXPECTED_DATA_4),
        ("data_6", EXPECTED_DATA_6),
    ],
)
def test_all_ground_truth(data_key, expected):
    """Parametrized test validating ALL ground truth values for each data key."""
    clear_tables()

    result = seed_data([data_key])
    assert result.get("success"), f"Seed failed for {data_key}: {result}"

    actual = query_inference_fact(expected["inference_id"])
    assert actual, f"No InferenceFact row for {data_key}"

    mismatches = []
    for col, expected_val in expected.items():
        if col in SKIP_COLUMNS:
            continue
        actual_val = actual.get(col)
        if not compare_values(expected_val, actual_val, col):
            mismatches.append(f"{col}: expected={expected_val!r}, actual={actual_val!r}")

    assert not mismatches, f"Mismatches in {data_key}:\n" + "\n".join(mismatches)


# =============================================================================
# BLOCKING EVENT DATA TEST
# =============================================================================
# Test data for blocked-only requests (no inference span, only gateway_analytics with blocking event)

EXPECTED_BLOCKED_DATA = {
    # Core identifiers (from gateway_analytics span)
    "trace_id": "blocked0000000000000000000000001",
    "inference_id": None,  # Blocked requests don't have inference_id
    "project_id": "019787c1-3de1-7b50-969b-e0a58514b6a1",
    "endpoint_id": "019787c1-3de1-7b50-969b-e0a58514b6a4",
    "model_id": "019787c1-3de1-7b50-969b-e0a58514b6a2",
    "api_key_id": None,
    "api_key_project_id": None,
    "user_id": None,
    # Status (blocked = failed)
    "is_success": False,
    "status_code": 403,
    "cost": None,
    "request_ip": None,
    "response_analysis": None,
    # Error fields
    "error_code": "BLOCKED",
    "error_message": None,
    "error_type": None,
    # Model inference fields (NULL for blocked requests)
    "model_inference_id": None,
    "model_name": None,
    "model_provider": None,
    "endpoint_type": "blocked",
    "input_tokens": 0,
    "output_tokens": 0,
    "response_time_ms": None,
    "ttft_ms": None,
    "cached": False,
    "finish_reason": None,
    "model_inference_timestamp": None,
    "system_prompt": None,
    "guardrail_scan_summary": None,
    # Chat inference fields (NULL for blocked requests)
    "chat_inference_id": None,
    "episode_id": None,
    "function_name": None,
    "variant_name": None,
    "processing_time_ms": None,
    "tags": None,
    "inference_params": None,
    "extra_body": None,
    "tool_params": None,
    # Gateway analytics
    "device_type": "desktop",
    "browser_name": "PostmanRuntime",
    "browser_version": "7.51",
    "os_name": "Other",
    "os_version": None,
    "is_bot": False,
    "method": "POST",
    "path": "/v1/chat/completions",
    "protocol_version": "HTTP/1.1",
    "user_agent": "PostmanRuntime/7.51.0",
    "gateway_processing_ms": 5,
    "total_duration_ms": 5,
    "is_blocked": True,  # Always true for blocked requests
    "block_reason": "rate_limit_exceeded",
    "block_rule_id": "019b971a-5a01-7000-a001-a10000000001",
    "client_ip": "192.168.1.50",
    "proxy_chain": None,
    "query_params": None,
    "body_size": 256,
    "response_size": None,
    "request_headers": '{"content-type":"application/json","accept":"*/*"}',
    "response_headers": '{"content-type":"application/json"}',
    "gateway_tags": "{}",
    # Geo fields
    "country_code": "CN",
    "country_name": "China",
    "region": "Beijing",
    "city": "Beijing",
    "latitude": 39.9042,
    "longitude": 116.4074,
    "timezone": "Asia/Shanghai",
    "asn": 4808,
    "isp": "China Unicom",
    "model_version": None,
    "routing_decision": None,
    # Blocking event data
    "blocking_event_id": "019b971a-6a01-7000-a001-a10000000001",
    "rule_id": "019b971a-5a01-7000-a001-a10000000001",
    "rule_type": "rate_limit",
    "rule_name": "API Rate Limit (100/min)",
    "rule_priority": 100,
    "block_reason_detail": "Rate limit exceeded: 101 requests in 60 seconds",
    "action_taken": "block",
}


def query_blocked_inference_fact(trace_id: str) -> dict:
    """Query InferenceFact for a blocked request by trace_id."""
    query = f"""
    SELECT *
    FROM {DATABASE}.InferenceFact
    WHERE trace_id = '{trace_id}' AND is_blocked = true
    FORMAT JSONEachRow
    """
    result = execute_query(query)
    if not result:
        return {}
    return json.loads(result)


class TestInferenceFactBlocking:
    """Test blocking event data in InferenceFact."""

    @pytest.mark.integration
    def test_blocking_columns_exist_in_schema(self):
        """Verify that blocking columns exist in InferenceFact schema."""
        query = f"""
        SELECT name
        FROM system.columns
        WHERE database = '{DATABASE}' AND table = 'InferenceFact'
        AND name IN (
            'blocking_event_id', 'rule_id', 'rule_type', 'rule_name',
            'rule_priority', 'block_reason_detail', 'action_taken', 'blocked_at'
        )
        ORDER BY name
        """
        result = execute_query(query)
        columns = set(result.strip().split('\n')) if result else set()

        expected_columns = {
            'blocking_event_id', 'rule_id', 'rule_type', 'rule_name',
            'rule_priority', 'block_reason_detail', 'action_taken', 'blocked_at'
        }

        assert columns == expected_columns, f"Missing columns: {expected_columns - columns}"

    @pytest.mark.integration
    def test_rollup_tables_have_blocking_columns(self):
        """Verify that rollup tables have block_count and unique_blocked_ips columns."""
        for table in ['InferenceMetrics5m', 'InferenceMetrics1h', 'InferenceMetrics1d']:
            query = f"""
            SELECT name
            FROM system.columns
            WHERE database = '{DATABASE}' AND table = '{table}'
            AND name IN ('block_count', 'unique_blocked_ips')
            ORDER BY name
            """
            result = execute_query(query)
            columns = set(result.strip().split('\n')) if result else set()

            assert 'block_count' in columns, f"Missing block_count in {table}"
            assert 'unique_blocked_ips' in columns, f"Missing unique_blocked_ips in {table}"

    @pytest.mark.integration
    def test_blocking_mv_exists(self):
        """Verify that mv_otel_blocking_to_inference_fact MV exists."""
        query = f"""
        SELECT name
        FROM system.tables
        WHERE database = '{DATABASE}'
        AND name = 'mv_otel_blocking_to_inference_fact'
        """
        result = execute_query(query)
        assert result.strip() == 'mv_otel_blocking_to_inference_fact', \
            "mv_otel_blocking_to_inference_fact MV not found"

    @pytest.mark.integration
    def test_is_blocked_index_exists(self):
        """Verify that is_blocked index exists for efficient filtering."""
        query = f"""
        SELECT name
        FROM system.data_skipping_indices
        WHERE database = '{DATABASE}'
        AND table = 'InferenceFact'
        AND name = 'idx_is_blocked'
        """
        result = execute_query(query)
        assert result.strip() == 'idx_is_blocked', "idx_is_blocked index not found"

    @pytest.mark.integration
    def test_rule_id_index_exists(self):
        """Verify that rule_id index exists for efficient filtering."""
        query = f"""
        SELECT name
        FROM system.data_skipping_indices
        WHERE database = '{DATABASE}'
        AND table = 'InferenceFact'
        AND name = 'idx_rule_id'
        """
        result = execute_query(query)
        assert result.strip() == 'idx_rule_id', "idx_rule_id index not found"
