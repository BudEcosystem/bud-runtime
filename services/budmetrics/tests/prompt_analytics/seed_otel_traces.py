"""Seeder for prompt analytics OTel traces test data.

This module loads OTel trace data from JSON fixtures and inserts them
into ClickHouse for testing the prompt analytics pipeline.

Can be run standalone from CLI:
    python seed_otel_traces.py --clear --verify
    python seed_otel_traces.py --data-keys response_success_1 chat_success
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent.parent / ".env")

DATA_FILE = Path(__file__).parent / "data" / "otel_traces_prompt_analytics.json"
DEFAULT_DATABASE = os.getenv("CLICKHOUSE_DB_NAME", "default_v8")
DEFAULT_CONTAINER = os.getenv("CLICKHOUSE_CONTAINER", "otel-clickhouse")


def load_trace_data() -> dict[str, list[dict]]:
    """Load trace data from the JSON fixture file."""
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


def generate_insert_sql(spans: list[dict], database: str = DEFAULT_DATABASE) -> str:
    """Generate INSERT SQL for spans."""
    columns = (
        "Timestamp, TraceId, SpanId, ParentSpanId, TraceState, SpanName, "
        "SpanKind, ServiceName, ResourceAttributes, ScopeName, ScopeVersion, "
        "SpanAttributes, Duration, StatusCode, StatusMessage, "
        "`Events.Timestamp`, `Events.Name`, `Events.Attributes`, "
        "`Links.TraceId`, `Links.SpanId`, `Links.TraceState`, `Links.Attributes`"
    )
    values = [span_to_values(span) for span in spans]
    return f"INSERT INTO {database}.otel_traces ({columns}) VALUES {', '.join(values)}"


def seed_otel_traces(
    data_keys: list[str] | None = None,
    database: str = DEFAULT_DATABASE,
    container: str = DEFAULT_CONTAINER,
) -> dict:
    """Seed otel_traces table with data from JSON fixture.

    Args:
        data_keys: List of data keys to insert (e.g., ['response_success_1', 'chat_success']).
                   If None, inserts all data.
        database: ClickHouse database name
        container: Docker container name for ClickHouse

    Returns:
        dict with seed results
    """
    data = load_trace_data()

    if data_keys is None:
        data_keys = list(data.keys())

    all_spans = []
    for key in data_keys:
        if key in data:
            all_spans.extend(data[key])

    if not all_spans:
        return {"error": "No spans to insert", "data_keys": data_keys}

    sql = generate_insert_sql(all_spans, database)

    # Write SQL to temp file for debugging (not used in execution)
    sql_file = Path("/tmp/prompt_analytics_seed.sql")  # nosec B108
    sql_file.write_text(sql)

    # Execute via docker
    cmd = ["docker", "exec", "-i", container, "clickhouse-client", "--queries-file", "/dev/stdin"]

    result = subprocess.run(cmd, input=sql, capture_output=True, text=True)

    if result.returncode != 0:
        return {
            "error": f"Failed to seed data: {result.stderr}",
            "data_keys": data_keys,
            "spans_attempted": len(all_spans),
        }

    # Extract trace IDs and inference IDs for verification
    trace_ids = list({span["TraceId"] for span in all_spans})
    inference_ids = []
    for span in all_spans:
        attrs = span.get("SpanAttributes", {})
        if isinstance(attrs, dict):
            inf_id = (
                attrs.get("model_inference_details.inference_id")
                or attrs.get("gateway_analytics.inference_id")
                or attrs.get("gen_ai.inference_id")
            )
            if inf_id:
                inference_ids.append(inf_id)

    return {
        "success": True,
        "data_keys": data_keys,
        "spans_inserted": len(all_spans),
        "trace_ids": trace_ids,
        "inference_ids": list(set(inference_ids)),
        "database": database,
    }


def verify_seeded_data(
    database: str = DEFAULT_DATABASE,
    container: str = DEFAULT_CONTAINER,
) -> dict:
    """Verify that seeded data was processed by MaterializedViews."""
    queries = {
        "otel_traces": f"SELECT count(*) FROM {database}.otel_traces",
        "InferenceFact": f"SELECT count(*) FROM {database}.InferenceFact",
        "InferenceMetrics5m": f"SELECT count(*) FROM {database}.InferenceMetrics5m",
        "InferenceMetrics1h": f"SELECT count(*) FROM {database}.InferenceMetrics1h",
        "InferenceMetrics1d": f"SELECT count(*) FROM {database}.InferenceMetrics1d",
    }

    results = {}
    for name, query in queries.items():
        cmd = ["docker", "exec", container, "clickhouse-client", "--query", query]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            results[name] = int(result.stdout.strip())
        else:
            results[name] = f"ERROR: {result.stderr}"

    return results


def clear_tables(
    database: str = DEFAULT_DATABASE,
    container: str = DEFAULT_CONTAINER,
) -> dict:
    """Clear all data from otel_traces and derived tables."""
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
        cmd = ["docker", "exec", container, "clickhouse-client", "--query", f"TRUNCATE TABLE {database}.{table}"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            results[table] = "cleared"
        else:
            results[table] = f"ERROR: {result.stderr}"

    return results


def execute_query(
    query: str,
    format: str = "",
    database: str = DEFAULT_DATABASE,
    container: str = DEFAULT_CONTAINER,
) -> str:
    """Execute ClickHouse query via docker exec.

    Args:
        query: SQL query to execute
        format: Optional output format (e.g., "JSONEachRow", "TabSeparated")
        database: ClickHouse database name
        container: Docker container name

    Returns:
        Query output as string

    Raises:
        RuntimeError: If query execution fails
    """
    format_suffix = f" FORMAT {format}" if format else ""
    cmd = ["docker", "exec", container, "clickhouse-client", "--database", database, "--query", query + format_suffix]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Query failed: {result.stderr}\nQuery: {query[:500]}")
    return result.stdout.strip()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed prompt analytics OTel traces from JSON fixture")
    parser.add_argument(
        "--data-keys",
        "-d",
        nargs="+",
        default=None,
        help="Data keys to insert (e.g., response_success_1 chat_success). Default: all",
    )
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="ClickHouse database")
    parser.add_argument("--container", default=DEFAULT_CONTAINER, help="Docker container")
    parser.add_argument("--verify", action="store_true", help="Verify after seeding")
    parser.add_argument("--clear", action="store_true", help="Clear tables before seeding")
    parser.add_argument("--list-keys", action="store_true", help="List available data keys and exit")

    args = parser.parse_args()

    if args.list_keys:
        data = load_trace_data()
        print("Available data keys:")
        for key, spans in data.items():
            print(f"  {key}: {len(spans)} spans")
        exit(0)

    if args.clear:
        print("Clearing tables...")
        clear_result = clear_tables(args.database, args.container)
        for table, status in clear_result.items():
            print(f"  {table}: {status}")
        print()

    print(f"Seeding data to {args.database}...")
    result = seed_otel_traces(data_keys=args.data_keys, database=args.database, container=args.container)

    if result.get("error"):
        print(f"Error: {result['error']}")
    else:
        print(f"Inserted {result['spans_inserted']} spans")
        print(f"Data keys: {result['data_keys']}")
        print(f"Trace IDs: {result['trace_ids']}")
        if result.get("inference_ids"):
            print(f"Inference IDs: {result['inference_ids']}")

    if args.verify:
        print("\nVerifying data...")
        counts = verify_seeded_data(args.database, args.container)
        for table, count in counts.items():
            print(f"  {table}: {count}")
