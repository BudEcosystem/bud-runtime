"""Generate additional test scenarios for prompt distribution testing.

This script generates new test data scenarios by varying:
- Timestamps (for different concurrency levels)
- Token counts (input_tokens, output_tokens)
- Prompt IDs (for filtering tests)
- Durations and TTFT values

Run: python generate_test_data.py
Output: Merges new scenarios into otel_traces_prompt_distribution.json
"""

import copy
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

# File paths
DATA_DIR = Path(__file__).parent / "data"
DATA_FILE = DATA_DIR / "otel_traces_prompt_distribution.json"

# Test constants
TEST_PROJECT_ID = "119787c1-3de1-7b50-969b-e0a58514b6a4"
TEST_ENDPOINT_ID = "119787c1-3de1-7b50-969b-e0a58514b6a2"
TEST_PROMPT_ID = "119787c1-3de1-7b50-969b-e0a58514b6a1"
TEST_PROMPT_ID_2 = "219787c1-3de1-7b50-969b-e0a58514b6a1"

# Base timestamp for new scenarios (different from existing data to avoid conflicts)
BASE_TIME = datetime(2026, 1, 31, 10, 36, 0)


def load_template() -> list[dict]:
    """Load the first concurrent_request as template."""
    with open(DATA_FILE) as f:
        data = json.load(f)
    return data["concurrent_request_1"]


def generate_trace_id() -> str:
    """Generate a random 32-character hex trace ID."""
    return uuid4().hex


def generate_span_id() -> str:
    """Generate a random 16-character hex span ID."""
    return uuid4().hex[:16]


def format_timestamp(dt: datetime, microseconds: int = 0) -> str:
    """Format datetime as ClickHouse timestamp string."""
    ts = dt + timedelta(microseconds=microseconds)
    return ts.strftime("%Y-%m-%d %H:%M:%S.") + f"{ts.microsecond:06d}000"


def format_iso_timestamp(dt: datetime, microseconds: int = 0) -> str:
    """Format datetime as ISO timestamp with timezone."""
    ts = dt + timedelta(microseconds=microseconds)
    return ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond:06d}+00:00"


def create_minimal_span(
    timestamp: datetime,
    trace_id: str,
    span_id: str,
    parent_span_id: str,
    span_name: str,
    project_id: str,
    endpoint_id: str,
    prompt_id: str,
    input_tokens: int,
    output_tokens: int,
    total_duration_ms: int,
    ttft_ms: int = 250,
    response_time_ms: int | None = None,
) -> dict[str, Any]:
    """Create a minimal gateway_analytics span with required attributes."""
    if response_time_ms is None:
        response_time_ms = total_duration_ms - 100  # Default to slightly less than total

    duration_ns = total_duration_ms * 1_000_000

    # Calculate request arrival and forward times
    request_arrival = format_iso_timestamp(timestamp)
    response_time = format_iso_timestamp(timestamp, microseconds=total_duration_ms * 1000)

    span_attributes = {
        "bud.endpoint_id": endpoint_id,
        "bud.project_id": project_id,
        "bud.prompt_id": prompt_id,
        "busy_ns": str(total_duration_ms * 10000),
        "gateway_analytics.browser_name": "TestClient",
        "gateway_analytics.browser_version": "1.0",
        "gateway_analytics.client_ip": "127.0.0.1",
        "gateway_analytics.device_type": "desktop",
        "gateway_analytics.gateway_processing_ms": "5",
        "gateway_analytics.id": str(uuid4()),
        "gateway_analytics.is_bot": "false",
        "gateway_analytics.method": "POST",
        "gateway_analytics.os_name": "Linux",
        "gateway_analytics.path": "/v1/responses",
        "gateway_analytics.project_id": project_id,
        "gateway_analytics.prompt_id": prompt_id,
        "gateway_analytics.prompt_version": "1",
        "gateway_analytics.protocol_version": "HTTP/1.1",
        "gateway_analytics.request_headers": '{"accept":"*/*","content-type":"application/json"}',
        "gateway_analytics.request_timestamp": request_arrival,
        "gateway_analytics.response_headers": '{"content-type":"application/json"}',
        "gateway_analytics.response_timestamp": response_time,
        "gateway_analytics.status_code": "200",
        "gateway_analytics.tags": "{}",
        "gateway_analytics.total_duration_ms": str(total_duration_ms),
        "gateway_analytics.user_agent": "TestClient/1.0",
        "gen_ai.usage.input_tokens": str(input_tokens),
        "gen_ai.usage.output_tokens": str(output_tokens),
        "gen_ai.usage.total_tokens": str(input_tokens + output_tokens),
        "gen_ai.request_arrival_time": request_arrival,
        "gen_ai.request_forward_time": response_time,
        "gen_ai.response_time_ms": str(response_time_ms),
        "gen_ai.ttft_ms": str(ttft_ms),
        "gen_ai.processing_time_ms": str(response_time_ms),
        "idle_ns": str(duration_ns - total_duration_ms * 10000),
        "level": "INFO",
        "thread.id": "2",
        "thread.name": "tokio-runtime-worker",
        "bud.api_key_id": "019787c1-3de1-7b50-969b-e0a58514aaaa",
        "bud.api_key_project_id": "019787c1-3de1-7b50-969b-e0a58514bbbb",
        "bud.user_id": "019787c1-3de1-7b50-969b-e0a58514cccc",
    }

    return {
        "Timestamp": format_timestamp(timestamp),
        "TraceId": trace_id,
        "SpanId": span_id,
        "ParentSpanId": parent_span_id,
        "TraceState": "",
        "SpanName": span_name,
        "SpanKind": "Internal",
        "ServiceName": "budgateway",
        "ResourceAttributes": {"service.name": "budgateway"},
        "ScopeName": "budgateway",
        "ScopeVersion": "",
        "SpanAttributes": span_attributes,
        "Duration": duration_ns,
        "StatusCode": "Unset",
        "StatusMessage": "",
        "Events.Timestamp": [],
        "Events.Name": [],
        "Events.Attributes": [],
        "Links.TraceId": [],
        "Links.SpanId": [],
        "Links.TraceState": [],
        "Links.Attributes": [],
    }


def create_child_span(
    parent: dict,
    span_name: str,
    offset_microseconds: int = 1000,
) -> dict[str, Any]:
    """Create a child span from a parent span."""
    child = copy.deepcopy(parent)
    child["SpanId"] = generate_span_id()
    child["ParentSpanId"] = parent["SpanId"]
    child["SpanName"] = span_name

    # Adjust timestamp slightly
    base_ts = datetime.strptime(parent["Timestamp"][:26], "%Y-%m-%d %H:%M:%S.%f")
    child["Timestamp"] = format_timestamp(base_ts, offset_microseconds)

    return child


def generate_high_concurrency_burst() -> dict[str, list[dict]]:
    """Generate 6 requests in the same second for high concurrency testing.

    All requests have timestamps within the same second to test concurrency=6 bucket.
    """
    base_time = BASE_TIME + timedelta(seconds=10)  # 10:36:10
    scenarios = {}

    for i in range(6):
        key = f"high_concurrency_{i+1}"
        trace_id = generate_trace_id()
        span_id = generate_span_id()

        # Vary microseconds within the same second
        microseconds = i * 100000  # 0, 100ms, 200ms, etc.
        timestamp = base_time + timedelta(microseconds=microseconds)

        # Vary token counts and durations slightly
        input_tokens = 500 + i * 50
        output_tokens = 200 + i * 20
        total_duration = 2000 + i * 300
        ttft = 100 + i * 20

        root_span = create_minimal_span(
            timestamp=timestamp,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id="",
            span_name="gateway_analytics",
            project_id=TEST_PROJECT_ID,
            endpoint_id=TEST_ENDPOINT_ID,
            prompt_id=TEST_PROMPT_ID,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_duration_ms=total_duration,
            ttft_ms=ttft,
        )

        # Add a child span for more realistic trace
        child_span = create_child_span(root_span, "response_create_handler_observability")

        scenarios[key] = [root_span, child_span]

    return scenarios


def generate_low_concurrency_spread() -> dict[str, list[dict]]:
    """Generate 3 requests across 3 different seconds for concurrency=1 testing.

    Each request is in a different second, so each has concurrency=1.
    """
    base_time = BASE_TIME + timedelta(seconds=20)  # 10:36:20
    scenarios = {}

    for i in range(3):
        key = f"low_concurrency_{i+1}"
        trace_id = generate_trace_id()
        span_id = generate_span_id()

        # Each request in a different second
        timestamp = base_time + timedelta(seconds=i)

        input_tokens = 300 + i * 100
        output_tokens = 150 + i * 50
        total_duration = 1500 + i * 200
        ttft = 80 + i * 30

        root_span = create_minimal_span(
            timestamp=timestamp,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id="",
            span_name="gateway_analytics",
            project_id=TEST_PROJECT_ID,
            endpoint_id=TEST_ENDPOINT_ID,
            prompt_id=TEST_PROMPT_ID,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_duration_ms=total_duration,
            ttft_ms=ttft,
        )

        child_span = create_child_span(root_span, "response_create_handler_observability")
        scenarios[key] = [root_span, child_span]

    return scenarios


def generate_variable_load_pattern() -> dict[str, list[dict]]:
    """Generate variable load pattern: 1 request, then 3 concurrent, then 2 concurrent.

    Tests how distribution handles varying concurrency levels.
    """
    base_time = BASE_TIME + timedelta(seconds=30)  # 10:36:30
    scenarios = {}

    # Pattern: second 0 -> 1 request, second 1 -> 3 requests, second 2 -> 2 requests
    pattern = [(0, 1), (1, 3), (2, 2)]

    request_idx = 0
    for second_offset, count in pattern:
        for i in range(count):
            key = f"variable_load_{request_idx+1}"
            trace_id = generate_trace_id()
            span_id = generate_span_id()

            # Requests in same second have microsecond offsets
            microseconds = i * 50000
            timestamp = base_time + timedelta(seconds=second_offset, microseconds=microseconds)

            input_tokens = 400 + request_idx * 30
            output_tokens = 180 + request_idx * 15
            total_duration = 1800 + request_idx * 150
            ttft = 90 + request_idx * 10

            root_span = create_minimal_span(
                timestamp=timestamp,
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id="",
                span_name="gateway_analytics",
                project_id=TEST_PROJECT_ID,
                endpoint_id=TEST_ENDPOINT_ID,
                prompt_id=TEST_PROMPT_ID,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_duration_ms=total_duration,
                ttft_ms=ttft,
            )

            child_span = create_child_span(root_span, "response_create_handler_observability")
            scenarios[key] = [root_span, child_span]
            request_idx += 1

    return scenarios


def generate_multi_prompt_concurrent() -> dict[str, list[dict]]:
    """Generate concurrent requests for 2 different prompts.

    4 total requests: 2 for prompt_id_1, 2 for prompt_id_2, all in same second.
    This tests prompt_id filtering.
    """
    base_time = BASE_TIME + timedelta(seconds=40)  # 10:36:40
    scenarios = {}

    prompts = [TEST_PROMPT_ID, TEST_PROMPT_ID, TEST_PROMPT_ID_2, TEST_PROMPT_ID_2]

    for i, prompt_id in enumerate(prompts):
        key = f"multi_prompt_{i+1}"
        trace_id = generate_trace_id()
        span_id = generate_span_id()

        microseconds = i * 100000
        timestamp = base_time + timedelta(microseconds=microseconds)

        input_tokens = 350 + i * 40
        output_tokens = 170 + i * 25
        total_duration = 2100 + i * 250
        ttft = 120 + i * 25

        root_span = create_minimal_span(
            timestamp=timestamp,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id="",
            span_name="gateway_analytics",
            project_id=TEST_PROJECT_ID,
            endpoint_id=TEST_ENDPOINT_ID,
            prompt_id=prompt_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_duration_ms=total_duration,
            ttft_ms=ttft,
        )

        child_span = create_child_span(root_span, "response_create_handler_observability")
        scenarios[key] = [root_span, child_span]

    return scenarios


def generate_high_token_requests() -> dict[str, list[dict]]:
    """Generate requests with high token counts for token bucketing tests.

    Creates 4 requests with varying high token counts to test input_tokens/output_tokens bucketing.
    """
    base_time = BASE_TIME + timedelta(seconds=50)  # 10:36:50
    scenarios = {}

    # High token configurations: (input_tokens, output_tokens)
    token_configs = [
        (5000, 2000),   # High input, high output
        (10000, 500),   # Very high input, moderate output
        (1000, 4000),   # Moderate input, high output
        (8000, 3000),   # High both
    ]

    for i, (input_tokens, output_tokens) in enumerate(token_configs):
        key = f"high_tokens_{i+1}"
        trace_id = generate_trace_id()
        span_id = generate_span_id()

        # Spread across 2 seconds (2 per second for concurrency=2)
        second_offset = i // 2
        microseconds = (i % 2) * 200000
        timestamp = base_time + timedelta(seconds=second_offset, microseconds=microseconds)

        # Duration scales with token count
        total_duration = 3000 + (input_tokens + output_tokens) // 10
        ttft = 200 + input_tokens // 50

        root_span = create_minimal_span(
            timestamp=timestamp,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id="",
            span_name="gateway_analytics",
            project_id=TEST_PROJECT_ID,
            endpoint_id=TEST_ENDPOINT_ID,
            prompt_id=TEST_PROMPT_ID,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_duration_ms=total_duration,
            ttft_ms=ttft,
        )

        child_span = create_child_span(root_span, "response_create_handler_observability")
        scenarios[key] = [root_span, child_span]

    return scenarios


def generate_edge_case_requests() -> dict[str, list[dict]]:
    """Generate edge case requests for testing boundary conditions.

    Creates requests with:
    - Zero TTFT
    - Very low duration
    - Minimum tokens
    """
    base_time = BASE_TIME + timedelta(seconds=55)  # 10:36:55
    scenarios = {}

    edge_cases = [
        ("edge_zero_ttft", 100, 50, 500, 0),      # Zero TTFT
        ("edge_low_duration", 150, 75, 100, 10),  # Very low duration
        ("edge_min_tokens", 10, 5, 800, 50),      # Minimum tokens
    ]

    for i, (key, input_tokens, output_tokens, duration, ttft) in enumerate(edge_cases):
        trace_id = generate_trace_id()
        span_id = generate_span_id()

        timestamp = base_time + timedelta(seconds=i)

        root_span = create_minimal_span(
            timestamp=timestamp,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id="",
            span_name="gateway_analytics",
            project_id=TEST_PROJECT_ID,
            endpoint_id=TEST_ENDPOINT_ID,
            prompt_id=TEST_PROMPT_ID,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_duration_ms=duration,
            ttft_ms=ttft,
        )

        child_span = create_child_span(root_span, "response_create_handler_observability")
        scenarios[key] = [root_span, child_span]

    return scenarios


def main():
    """Generate all test scenarios and merge into JSON file."""
    # Load existing data
    with open(DATA_FILE) as f:
        existing_data = json.load(f)

    print(f"Loaded {len(existing_data)} existing scenarios")

    # Generate new scenarios
    new_scenarios = {}
    new_scenarios.update(generate_high_concurrency_burst())
    new_scenarios.update(generate_low_concurrency_spread())
    new_scenarios.update(generate_variable_load_pattern())
    new_scenarios.update(generate_multi_prompt_concurrent())
    new_scenarios.update(generate_high_token_requests())
    new_scenarios.update(generate_edge_case_requests())

    print(f"Generated {len(new_scenarios)} new scenarios:")
    for key, spans in new_scenarios.items():
        print(f"  {key}: {len(spans)} spans")

    # Merge with existing data
    merged_data = {**existing_data, **new_scenarios}

    # Write back
    with open(DATA_FILE, "w") as f:
        json.dump(merged_data, f, indent=2)

    print(f"\nTotal scenarios: {len(merged_data)}")
    print(f"Saved to {DATA_FILE}")

    # Print summary statistics
    total_spans = sum(len(spans) for spans in merged_data.values())
    print(f"Total spans: {total_spans}")


if __name__ == "__main__":
    main()
