"""Fixtures for prompt analytics integration tests.

This module provides shared fixtures for:
- Database connection via docker exec
- Table cleanup between tests
- Seeding otel_traces with test data
- Query helpers for InferenceFact and rollup tables
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# ClickHouse connection settings for docker-compose.otel.yml
DATABASE = os.getenv("CLICKHOUSE_DB_NAME", "default_v8")
CONTAINER = os.getenv("CLICKHOUSE_CONTAINER", "otel-clickhouse")

DATA_FILE = Path(__file__).parent / "data" / "otel_traces_prompt_analytics.json"


def execute_query(query: str, format: str = "") -> str:
    """Execute ClickHouse query via docker exec.

    Args:
        query: SQL query to execute
        format: Optional output format (e.g., "JSONEachRow", "TabSeparated")

    Returns:
        Query output as string

    Raises:
        RuntimeError: If query execution fails
    """
    format_suffix = f" FORMAT {format}" if format else ""
    cmd = [
        "docker", "exec", CONTAINER,
        "clickhouse-client",
        "--database", DATABASE,
        "--query", query + format_suffix
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Query failed: {result.stderr}\nQuery: {query[:500]}")
    return result.stdout.strip()


def clear_all_tables() -> dict[str, str]:
    """Clear all tables for clean test state.

    Returns:
        Dict mapping table name to status ("cleared" or error message)
    """
    tables = [
        "otel_traces",
        "InferenceFact",
        "InferenceMetrics5m",
        "InferenceMetrics1h",
        "InferenceMetrics1d",
        "otel_traces_trace_id_ts",
    ]
    results = {}
    for table in tables:
        try:
            execute_query(f"TRUNCATE TABLE {table}")
            results[table] = "cleared"
        except RuntimeError as e:
            results[table] = f"ERROR: {e}"
    return results


def load_test_data() -> dict[str, list[dict]]:
    """Load test data from JSON fixture.

    Returns:
        Dict mapping scenario key to list of span dicts
    """
    with open(DATA_FILE) as f:
        return json.load(f)


def format_map_value(value: dict | str) -> str:
    """Format a dict or string as ClickHouse Map format."""
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
    elif isinstance(value, dict):
        pairs = []
        for k, v in value.items():
            k_escaped = str(k).replace("\\", "\\\\").replace("'", "\\'")
            v_escaped = str(v).replace("\\", "\\\\").replace("'", "\\'")
            pairs.append(f"'{k_escaped}':'{v_escaped}'")
        return "{" + ",".join(pairs) + "}"
    return "{}"


def format_array(arr: list) -> str:
    """Format a list as ClickHouse Array format."""
    if not arr:
        return "[]"
    items = []
    for item in arr:
        if isinstance(item, dict):
            items.append(format_map_value(item))
        else:
            escaped = str(item).replace("\\", "\\\\").replace("'", "\\'")
            items.append(f"'{escaped}'")
    return "[" + ",".join(items) + "]"


def span_to_values(span: dict[str, Any]) -> str:
    """Convert a span dict to ClickHouse VALUES tuple."""
    def esc(val: Any) -> str:
        if val is None:
            return "''"
        s = str(val).replace("\\", "\\\\").replace("'", "\\'")
        return f"'{s}'"

    return (
        f"({esc(span.get('Timestamp', ''))}, "
        f"{esc(span.get('TraceId', ''))}, "
        f"{esc(span.get('SpanId', ''))}, "
        f"{esc(span.get('ParentSpanId', ''))}, "
        f"{esc(span.get('TraceState', ''))}, "
        f"{esc(span.get('SpanName', ''))}, "
        f"{esc(span.get('SpanKind', ''))}, "
        f"{esc(span.get('ServiceName', ''))}, "
        f"{format_map_value(span.get('ResourceAttributes', {}))}, "
        f"{esc(span.get('ScopeName', ''))}, "
        f"{esc(span.get('ScopeVersion', ''))}, "
        f"{format_map_value(span.get('SpanAttributes', {}))}, "
        f"{span.get('Duration', 0)}, "
        f"{esc(span.get('StatusCode', ''))}, "
        f"{esc(span.get('StatusMessage', ''))}, "
        f"{format_array(span.get('Events.Timestamp', []))}, "
        f"{format_array(span.get('Events.Name', []))}, "
        f"{format_array(span.get('Events.Attributes', []))}, "
        f"{format_array(span.get('Links.TraceId', []))}, "
        f"{format_array(span.get('Links.SpanId', []))}, "
        f"{format_array(span.get('Links.TraceState', []))}, "
        f"{format_array(span.get('Links.Attributes', []))})"
    )


def generate_insert_sql(spans: list[dict]) -> str:
    """Generate INSERT SQL for spans."""
    columns = (
        "Timestamp, TraceId, SpanId, ParentSpanId, TraceState, SpanName, "
        "SpanKind, ServiceName, ResourceAttributes, ScopeName, ScopeVersion, "
        "SpanAttributes, Duration, StatusCode, StatusMessage, "
        "`Events.Timestamp`, `Events.Name`, `Events.Attributes`, "
        "`Links.TraceId`, `Links.SpanId`, `Links.TraceState`, `Links.Attributes`"
    )
    values = [span_to_values(span) for span in spans]
    return f"INSERT INTO {DATABASE}.otel_traces ({columns}) VALUES {', '.join(values)}"


def seed_otel_traces(data_keys: list[str] | None = None) -> dict:
    """Seed otel_traces table with data from JSON fixture.

    Args:
        data_keys: List of scenario keys to insert (e.g., ['chat_success', 'response_prompt']).
                   If None, inserts all scenarios.

    Returns:
        Dict with seed results including success status, counts, and IDs
    """
    data = load_test_data()

    if data_keys is None:
        data_keys = list(data.keys())

    all_spans = []
    for key in data_keys:
        if key in data:
            all_spans.extend(data[key])

    if not all_spans:
        return {"error": "No spans to insert", "data_keys": data_keys}

    sql = generate_insert_sql(all_spans)

    # Execute via docker
    cmd = [
        "docker", "exec", "-i", CONTAINER,
        "clickhouse-client", "--queries-file", "/dev/stdin"
    ]

    result = subprocess.run(
        cmd,
        input=sql,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return {
            "error": f"Failed to seed data: {result.stderr}",
            "data_keys": data_keys,
            "spans_attempted": len(all_spans),
        }

    # Extract trace IDs and inference IDs for verification
    trace_ids = list(set(span["TraceId"] for span in all_spans))
    inference_ids = []
    for span in all_spans:
        attrs = span.get("SpanAttributes", {})
        if isinstance(attrs, dict):
            inf_id = (
                attrs.get("model_inference_details.inference_id") or
                attrs.get("gateway_analytics.inference_id") or
                attrs.get("gen_ai.inference_id")
            )
            if inf_id:
                inference_ids.append(inf_id)

    return {
        "success": True,
        "data_keys": data_keys,
        "spans_inserted": len(all_spans),
        "trace_ids": trace_ids,
        "inference_ids": list(set(inference_ids)),
        "database": DATABASE,
    }


def query_inference_fact(inference_id: str) -> dict | None:
    """Query InferenceFact by inference_id.

    Args:
        inference_id: The inference_id to query

    Returns:
        Dict of row data or None if not found
    """
    result = execute_query(
        f"SELECT * FROM InferenceFact WHERE toString(inference_id) = '{inference_id}'",
        format="JSONEachRow"
    )
    if not result:
        return None
    return json.loads(result.split('\n')[0])


def query_inference_fact_by_trace(trace_id: str) -> list[dict]:
    """Query all InferenceFact rows for a trace.

    Args:
        trace_id: The trace_id to query

    Returns:
        List of row dicts ordered by timestamp
    """
    result = execute_query(
        f"SELECT * FROM InferenceFact WHERE trace_id = '{trace_id}' ORDER BY timestamp",
        format="JSONEachRow"
    )
    if not result:
        return []
    return [json.loads(line) for line in result.split('\n') if line]


def query_rollup_5m(time_bucket: str | None = None, project_id: str | None = None) -> list[dict]:
    """Query InferenceMetrics5m with optional filters.

    Args:
        time_bucket: Optional time bucket filter
        project_id: Optional project_id filter

    Returns:
        List of row dicts
    """
    conditions = []
    if time_bucket:
        conditions.append(f"time_bucket = '{time_bucket}'")
    if project_id:
        conditions.append(f"toString(project_id) = '{project_id}'")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    result = execute_query(
        f"SELECT * FROM InferenceMetrics5m {where_clause}",
        format="JSONEachRow"
    )
    if not result:
        return []
    return [json.loads(line) for line in result.split('\n') if line]


# =============================================================================
# PYTEST FIXTURES
# =============================================================================


@pytest.fixture(scope="class")
def clean_db():
    """Clear all tables before each test class."""
    clear_all_tables()
    yield
    # Optional: clear after tests too for cleanliness


@pytest.fixture(scope="class")
def seeded_db(clean_db):
    """Seed ALL test data after cleaning DB.

    This fixture is for aggregate tests that need all scenarios.
    """
    result = seed_otel_traces()  # Seed all data
    assert result.get("success"), f"Seeding failed: {result}"
    # Wait for MVs to process
    time.sleep(1)
    yield result


@pytest.fixture(scope="function")
def clean_db_function():
    """Clear all tables before each test function (for per-scenario tests)."""
    clear_all_tables()
    yield


@pytest.fixture
def test_data() -> dict[str, list[dict]]:
    """Load test data fixture."""
    return load_test_data()
