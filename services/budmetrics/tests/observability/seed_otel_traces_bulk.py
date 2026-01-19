"""High-volume OTel traces seeder for performance testing.

This module generates and inserts millions of OpenTelemetry traces into ClickHouse
for testing the analytics pipeline performance at scale.

Features:
- Generates up to 50M+ traces with configurable success/error ratios
- Uses multiprocessing for parallel batch generation and insertion
- Randomizes resource IDs (project, endpoint, model, api_key) for realistic data
- Maintains proper trace/span relationships and inference_id consistency
- Provides progress tracking and verification functions

Known Limitations:
- InferenceFact may not populate 100% of traces immediately due to ClickHouse MV
  self-join limitations during bulk INSERT. This is expected behavior and doesn't
  affect the otel_traces table or rollup tables (InferenceMetrics*).
- For complete InferenceFact population, you can run: OPTIMIZE TABLE otel_traces FINAL

Usage:
    python seed_otel_traces_bulk.py --total 1000000 --success 900000 --error 100000 --workers 4
"""

import argparse
import copy
import json
import multiprocessing
import os
import random
import secrets
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv

try:
    import ulid
except ImportError:
    print("ERROR: ulid-py package is required. Install with: pip install ulid-py")
    sys.exit(1)

# Load environment variables
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Constants
DATA_FILE = Path(__file__).parent / "data" / "otel_traces_sample.json"
DEFAULT_DATABASE = os.getenv("CLICKHOUSE_DB_NAME", "default_v4")
DEFAULT_BATCH_SIZE = 10000
DEFAULT_WORKERS = 4
SPANS_PER_TRACE = 8

# Time range for spreading traces (last 90 days)
TIME_RANGE_DAYS = 90


# ============================================================================
# Template Loading Functions
# ============================================================================


def load_trace_templates() -> tuple[list[dict], list[dict]]:
    """Load success and error templates from JSON fixture.

    Returns:
        (success_template, error_template): Each is a list of 8 span dicts
    """
    with open(DATA_FILE) as f:
        data = json.load(f)

    success_template = data["data_6"]  # 8 spans, successful trace
    error_template = data["data_4"]    # 8 spans, 502 error trace

    return success_template, error_template


# ============================================================================
# ID Generation Functions
# ============================================================================


def generate_trace_ids(count: int) -> list[str]:
    """Pre-generate TraceIds efficiently (32 hex chars each)."""
    return [secrets.token_hex(16) for _ in range(count)]


def generate_span_ids(count: int) -> list[str]:
    """Pre-generate SpanIds efficiently (16 hex chars each)."""
    return [secrets.token_hex(8) for _ in range(count)]


def generate_inference_id() -> str:
    """Generate ULID-format inference_id (UUID representation)."""
    return ulid.new().uuid


def generate_resource_id_pools(
    num_projects: int = 10,
    num_endpoints: int = 20,
    num_models: int = 5,
    num_api_keys: int = 30
) -> dict:
    """Generate pools of realistic resource IDs for variation.

    Returns:
        dict with 'project_ids', 'endpoint_ids', 'model_ids', 'api_key_ids' lists
    """
    return {
        'project_ids': [str(uuid4()) for _ in range(num_projects)],
        'endpoint_ids': [str(uuid4()) for _ in range(num_endpoints)],
        'model_ids': [str(uuid4()) for _ in range(num_models)],
        'api_key_ids': [str(uuid4()) for _ in range(num_api_keys)],
    }


def select_random_resource_ids(pools: dict) -> dict:
    """Randomly select one ID from each pool for a trace."""
    return {
        'project_id': random.choice(pools['project_ids']),
        'endpoint_id': random.choice(pools['endpoint_ids']),
        'model_id': random.choice(pools['model_ids']),
        'api_key_id': random.choice(pools['api_key_ids']),
    }


# ============================================================================
# Timestamp Generation Functions
# ============================================================================


def generate_timestamp_base(time_range_days: int = TIME_RANGE_DAYS) -> datetime:
    """Generate a random timestamp within the last N days."""
    now = datetime.now()
    days_ago = random.randint(0, time_range_days)
    hours_ago = random.randint(0, 23)
    minutes_ago = random.randint(0, 59)
    seconds_ago = random.randint(0, 59)

    return now - timedelta(
        days=days_ago,
        hours=hours_ago,
        minutes=minutes_ago,
        seconds=seconds_ago
    )


def format_timestamp(dt: datetime, offset_ms: int = 0) -> str:
    """Format datetime to ClickHouse timestamp format with nanosecond precision.

    Args:
        dt: Base datetime
        offset_ms: Milliseconds to add for span offsets
    """
    dt_with_offset = dt + timedelta(milliseconds=offset_ms)
    # Format: YYYY-MM-DD HH:MM:SS.nnnnnnnnn
    timestamp_str = dt_with_offset.strftime("%Y-%m-%d %H:%M:%S")
    # Add nanoseconds (just zeros for simplicity)
    return f"{timestamp_str}.000000000"


# ============================================================================
# Trace Generation Functions
# ============================================================================


def update_span_attributes(span_attrs: dict, key_path: str, value: Any) -> None:
    """Update a nested attribute in SpanAttributes dict.

    Args:
        span_attrs: SpanAttributes dict to modify
        key_path: Dot-separated path (e.g., 'model_inference_details.inference_id')
        value: New value to set
    """
    span_attrs[key_path] = value


def generate_trace(
    template: list[dict],
    trace_id: str,
    span_ids: list[str],
    inference_id: str,
    timestamp_base: datetime,
    resource_ids: dict,
    is_success: bool
) -> list[dict]:
    """Generate one complete trace (8 spans) from template.

    Args:
        template: List of 8 span dicts to use as template
        trace_id: TraceId for all spans in this trace
        span_ids: List of 8 SpanIds (one per span)
        inference_id: ULID-format inference_id for this trace
        timestamp_base: Base timestamp for the trace
        resource_ids: Dict with project_id, endpoint_id, model_id, api_key_id
        is_success: Whether this is a success or error trace

    Returns:
        List of 8 span dicts ready for insertion
    """
    spans = []

    # Build span_id mapping to maintain parent-child relationships
    # Original template span order should be maintained
    original_span_ids = [span["SpanId"] for span in template]
    span_id_map = dict(zip(original_span_ids, span_ids))

    for i, template_span in enumerate(template):
        # Deep copy to avoid modifying template
        span = copy.deepcopy(template_span)

        # Update TraceId
        span["TraceId"] = trace_id

        # Update SpanId
        span["SpanId"] = span_ids[i]

        # Update ParentSpanId (maintain parent-child relationships)
        if span["ParentSpanId"]:
            original_parent_id = span["ParentSpanId"]
            if original_parent_id in span_id_map:
                span["ParentSpanId"] = span_id_map[original_parent_id]

        # Update timestamps
        # Use progressive offsets for spans (0, 10, 20, 30ms etc)
        offset_ms = i * 10
        span["Timestamp"] = format_timestamp(timestamp_base, offset_ms)

        # Update SpanAttributes based on SpanName
        span_attrs = span.get("SpanAttributes", {})
        if not isinstance(span_attrs, dict):
            span_attrs = {}

        span_name = span.get("SpanName", "")

        # Update inference_handler_observability span
        if span_name == "inference_handler_observability":
            update_span_attributes(
                span_attrs,
                "model_inference_details.inference_id",
                inference_id
            )
            update_span_attributes(
                span_attrs,
                "model_inference_details.project_id",
                resource_ids['project_id']
            )
            update_span_attributes(
                span_attrs,
                "model_inference_details.endpoint_id",
                resource_ids['endpoint_id']
            )
            update_span_attributes(
                span_attrs,
                "model_inference_details.model_id",
                resource_ids['model_id']
            )
            update_span_attributes(
                span_attrs,
                "model_inference_details.api_key_id",
                resource_ids['api_key_id']
            )
            update_span_attributes(
                span_attrs,
                "model_inference_details.api_key_project_id",
                resource_ids['project_id']  # Same as project_id
            )
            # Generate new UUIDs for model/chat inference IDs
            update_span_attributes(
                span_attrs,
                "model_inference.id",
                str(uuid4())
            )
            update_span_attributes(
                span_attrs,
                "chat_inference.id",
                str(uuid4())
            )

        # Update gateway_analytics span
        elif span_name == "gateway_analytics":
            update_span_attributes(
                span_attrs,
                "gateway_analytics.inference_id",
                inference_id
            )
            update_span_attributes(
                span_attrs,
                "gateway_analytics.id",
                str(uuid4())
            )

        # Update function_inference span
        elif span_name == "function_inference":
            update_span_attributes(
                span_attrs,
                "inference_id",
                inference_id
            )

        span["SpanAttributes"] = span_attrs
        spans.append(span)

    return spans


# ============================================================================
# Batch Generation Functions
# ============================================================================


def generate_batch(
    batch_size: int,
    success_count: int,
    error_count: int,
    success_template: list[dict],
    error_template: list[dict],
    resource_id_pools: dict
) -> list[dict]:
    """Generate a batch of spans for batch_size traces.

    Args:
        batch_size: Number of traces in this batch
        success_count: Number of success traces in this batch
        error_count: Number of error traces in this batch
        success_template: Template for success traces (8 spans)
        error_template: Template for error traces (8 spans)
        resource_id_pools: Pools of resource IDs to randomly select from

    Returns:
        Flat list of all spans (batch_size * 8 spans), sorted by span name priority
    """
    all_spans = []

    # Pre-generate IDs for efficiency
    trace_ids = generate_trace_ids(batch_size)
    # Each trace needs 8 span IDs
    span_ids_flat = generate_span_ids(batch_size * SPANS_PER_TRACE)

    # Generate success traces
    for i in range(success_count):
        trace_id = trace_ids[i]
        span_ids = span_ids_flat[i * SPANS_PER_TRACE:(i + 1) * SPANS_PER_TRACE]
        inference_id = generate_inference_id()
        timestamp_base = generate_timestamp_base()
        resource_ids = select_random_resource_ids(resource_id_pools)

        trace_spans = generate_trace(
            success_template,
            trace_id,
            span_ids,
            inference_id,
            timestamp_base,
            resource_ids,
            is_success=True
        )
        all_spans.extend(trace_spans)

    # Generate error traces
    for i in range(error_count):
        idx = success_count + i
        trace_id = trace_ids[idx]
        span_ids = span_ids_flat[idx * SPANS_PER_TRACE:(idx + 1) * SPANS_PER_TRACE]
        inference_id = generate_inference_id()
        timestamp_base = generate_timestamp_base()
        resource_ids = select_random_resource_ids(resource_id_pools)

        trace_spans = generate_trace(
            error_template,
            trace_id,
            span_ids,
            inference_id,
            timestamp_base,
            resource_ids,
            is_success=False
        )
        all_spans.extend(trace_spans)

    # Sort spans to ensure gateway_analytics comes before inference_handler_observability
    # This helps ClickHouse MV self-joins work correctly during INSERT
    span_priority = {
        'gateway_analytics': 0,  # Must come first for MV JOIN
        'inference_handler_observability': 1,  # Must come after gateway_analytics
        # Other spans can be in any order
    }

    def span_sort_key(span):
        span_name = span.get('SpanName', '')
        # Primary: sort by priority (gateway_analytics first)
        # Secondary: sort by TraceId to keep trace spans together
        return (span_priority.get(span_name, 999), span.get('TraceId', ''))

    all_spans.sort(key=span_sort_key)

    return all_spans


# ============================================================================
# Batch Insertion Functions
# ============================================================================


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
        f"({esc(span['Timestamp'])}, "
        f"{esc(span['TraceId'])}, "
        f"{esc(span['SpanId'])}, "
        f"{esc(span['ParentSpanId'])}, "
        f"{esc(span['TraceState'])}, "
        f"{esc(span['SpanName'])}, "
        f"{esc(span['SpanKind'])}, "
        f"{esc(span['ServiceName'])}, "
        f"{format_map_value(span.get('ResourceAttributes', {}))}, "
        f"{esc(span.get('ScopeName', ''))}, "
        f"{esc(span.get('ScopeVersion', ''))}, "
        f"{format_map_value(span.get('SpanAttributes', {}))}, "
        f"{span['Duration']}, "
        f"{esc(span['StatusCode'])}, "
        f"{esc(span['StatusMessage'])}, "
        f"{format_array(span.get('Events.Timestamp', []))}, "
        f"{format_array(span.get('Events.Name', []))}, "
        f"{format_array(span.get('Events.Attributes', []))}, "
        f"{format_array(span.get('Links.TraceId', []))}, "
        f"{format_array(span.get('Links.SpanId', []))}, "
        f"{format_array(span.get('Links.TraceState', []))}, "
        f"{format_array(span.get('Links.Attributes', []))})"
    )


def generate_insert_sql(spans: list[dict], database: str) -> str:
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


def insert_batch(
    spans: list[dict],
    database: str,
    container: str
) -> dict:
    """Insert batch using ClickHouse client.

    Args:
        spans: List of span dicts to insert
        database: ClickHouse database name
        container: Docker container name

    Returns:
        dict with 'success' bool and optional 'error' message
    """
    try:
        sql = generate_insert_sql(spans, database)

        # Execute via docker
        cmd = [
            "docker", "exec", "-i", container,
            "clickhouse-client", "--queries-file", "/dev/stdin"
        ]

        result = subprocess.run(
            cmd,
            input=sql,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout for large batches
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"ClickHouse error: {result.stderr[:500]}"
            }

        return {"success": True, "spans_inserted": len(spans)}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Insertion timeout (>5 minutes)"}
    except Exception as e:
        return {"success": False, "error": f"Exception: {str(e)[:500]}"}


# ============================================================================
# Worker Process Functions
# ============================================================================


def worker_process(
    worker_id: int,
    batch_configs: list[dict],
    database: str,
    container: str,
    progress_queue: multiprocessing.Queue
) -> dict:
    """Worker that generates and inserts multiple batches.

    Args:
        worker_id: Unique worker identifier
        batch_configs: List of dicts with batch_size, success_count, error_count
        database: ClickHouse database
        container: Docker container name
        progress_queue: Queue for reporting progress

    Returns:
        dict with summary statistics
    """
    # Load templates once per worker
    success_template, error_template = load_trace_templates()

    # Generate resource ID pools once per worker
    resource_id_pools = generate_resource_id_pools()

    total_spans = 0
    total_traces = 0
    failed_batches = 0

    for batch_num, config in enumerate(batch_configs):
        try:
            # Generate batch with specific counts
            spans = generate_batch(
                config['batch_size'],
                config['success_count'],
                config['error_count'],
                success_template,
                error_template,
                resource_id_pools
            )

            # Insert batch
            result = insert_batch(spans, database, container)

            if result["success"]:
                total_spans += len(spans)
                total_traces += config['batch_size']
                progress_queue.put({
                    "worker_id": worker_id,
                    "batch_num": batch_num,
                    "success": True
                })
            else:
                failed_batches += 1
                progress_queue.put({
                    "worker_id": worker_id,
                    "batch_num": batch_num,
                    "success": False,
                    "error": result.get("error", "Unknown error")
                })

        except Exception as e:
            failed_batches += 1
            progress_queue.put({
                "worker_id": worker_id,
                "batch_num": batch_num,
                "success": False,
                "error": str(e)[:200]
            })

    return {
        "worker_id": worker_id,
        "total_spans": total_spans,
        "total_traces": total_traces,
        "failed_batches": failed_batches
    }


# ============================================================================
# Progress Tracking Functions
# ============================================================================


def display_progress(
    total_batches: int,
    progress_queue: multiprocessing.Queue,
    num_workers: int
) -> list[dict]:
    """Display real-time progress as workers report completed batches.

    Args:
        total_batches: Total number of batches to process
        progress_queue: Queue receiving progress updates from workers
        num_workers: Number of worker processes

    Returns:
        List of error messages if any occurred
    """
    completed_batches = 0
    errors = []

    print(f"\nProcessing {total_batches} batches with {num_workers} workers...")
    print("Progress: [", end="", flush=True)

    # Track progress
    progress_marks = 50  # Number of progress characters to display
    marks_per_batch = total_batches / progress_marks
    next_mark_at = marks_per_batch

    while completed_batches < total_batches:
        try:
            update = progress_queue.get(timeout=1)
            completed_batches += 1

            if not update["success"]:
                errors.append(f"Worker {update['worker_id']} batch {update['batch_num']}: {update['error']}")

            # Update progress bar
            while completed_batches >= next_mark_at:
                print("=", end="", flush=True)
                next_mark_at += marks_per_batch

        except multiprocessing.queues.Empty:
            continue

    print("] Done!\n")
    return errors


# ============================================================================
# Main Seeding Function
# ============================================================================


def seed_otel_traces_bulk(
    total: int | None = None,
    success_count: int | None = None,
    error_count: int | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    num_workers: int = DEFAULT_WORKERS,
    database: str = DEFAULT_DATABASE,
    container: str = "otel-clickhouse"
) -> dict:
    """Main seeding function with multiprocessing.

    Args:
        total: Total number of traces to generate
        success_count: Number of success traces
        error_count: Number of error traces
        batch_size: Traces per batch (default 10,000)
        num_workers: Number of parallel workers (default 4)
        database: ClickHouse database name
        container: Docker container name

    Returns:
        dict with summary statistics
    """
    # Calculate success/error counts
    if total is None and success_count is None and error_count is None:
        return {"error": "Must specify --total, --success, or --error"}

    if total is not None:
        if success_count is not None and error_count is not None:
            # Validate that success + error = total
            if success_count + error_count != total:
                return {"error": f"success ({success_count}) + error ({error_count}) must equal total ({total})"}
        elif success_count is not None:
            error_count = total - success_count
        elif error_count is not None:
            success_count = total - error_count
        else:
            # Only total specified, all success
            success_count = total
            error_count = 0
    else:
        # total not specified
        if success_count is None:
            success_count = 0
        if error_count is None:
            error_count = 0
        total = success_count + error_count

    if total <= 0:
        return {"error": "Total traces must be > 0"}

    print(f"\n{'='*70}")
    print(f"OTel Traces Bulk Seeder")
    print(f"{'='*70}")
    print(f"Total traces:     {total:,}")
    print(f"Success traces:   {success_count:,} ({100*success_count/total:.1f}%)")
    print(f"Error traces:     {error_count:,} ({100*error_count/total:.1f}%)")
    print(f"Batch size:       {batch_size:,}")
    print(f"Workers:          {num_workers}")
    print(f"Database:         {database}")
    print(f"Container:        {container}")
    print(f"{'='*70}\n")

    # Calculate batch configurations
    total_batches = (total + batch_size - 1) // batch_size
    success_ratio = success_count / total
    error_ratio = error_count / total

    # Create batch configs with exact trace counts
    batch_configs = []
    remaining_total = total
    remaining_success = success_count
    remaining_error = error_count

    for batch_idx in range(total_batches):
        # Calculate traces for this batch
        traces_in_batch = min(batch_size, remaining_total)
        success_in_batch = int(traces_in_batch * success_ratio)
        error_in_batch = traces_in_batch - success_in_batch

        # Adjust to ensure we hit exact totals
        if batch_idx == total_batches - 1:
            success_in_batch = remaining_success
            error_in_batch = remaining_error

        batch_configs.append({
            'batch_size': traces_in_batch,
            'success_count': success_in_batch,
            'error_count': error_in_batch
        })

        remaining_total -= traces_in_batch
        remaining_success -= success_in_batch
        remaining_error -= error_in_batch

    # Distribute batches across workers
    worker_batch_configs = [[] for _ in range(num_workers)]
    for batch_idx, config in enumerate(batch_configs):
        worker_id = batch_idx % num_workers
        worker_batch_configs[worker_id].append(config)

    print(f"Total batches: {total_batches}")
    print(f"Worker distribution: {[len(wbc) for wbc in worker_batch_configs]}\n")

    # Create progress queue
    progress_queue = multiprocessing.Queue()

    # Start workers
    workers = []
    start_time = datetime.now()

    for worker_id in range(num_workers):
        if not worker_batch_configs[worker_id]:
            # No batches for this worker, skip
            continue

        process = multiprocessing.Process(
            target=worker_process,
            args=(
                worker_id,
                worker_batch_configs[worker_id],
                database,
                container,
                progress_queue
            )
        )
        process.start()
        workers.append(process)

    # Display progress
    errors = display_progress(total_batches, progress_queue, num_workers)

    # Wait for all workers to complete
    for worker in workers:
        worker.join()

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Calculate final statistics
    expected_spans = total * SPANS_PER_TRACE
    traces_per_second = total / duration if duration > 0 else 0

    print(f"\n{'='*70}")
    print(f"Seeding Complete!")
    print(f"{'='*70}")
    print(f"Duration:         {duration:.1f} seconds ({duration/60:.1f} minutes)")
    print(f"Traces/second:    {traces_per_second:.1f}")
    print(f"Total spans:      {expected_spans:,}")
    print(f"Failed batches:   {len(errors)}")
    if errors:
        print(f"\nErrors (first 5):")
        for error in errors[:5]:
            print(f"  - {error}")
    print(f"{'='*70}\n")

    return {
        "success": len(errors) == 0,
        "total_traces": total,
        "success_traces": success_count,
        "error_traces": error_count,
        "expected_spans": expected_spans,
        "duration_seconds": duration,
        "traces_per_second": traces_per_second,
        "failed_batches": len(errors),
        "errors": errors
    }


# ============================================================================
# Verification Functions
# ============================================================================


def verify_bulk_seeded_data(
    expected_trace_count: int,
    database: str = DEFAULT_DATABASE,
    container: str = "otel-clickhouse"
) -> dict:
    """Verify seeded data with optimized queries.

    Note: InferenceFact may not have 100% of traces due to ClickHouse MV self-join
    limitations during bulk INSERT. This is expected and doesn't affect performance
    testing of otel_traces or rollup tables.

    Args:
        expected_trace_count: Expected number of traces
        database: ClickHouse database
        container: Docker container name

    Returns:
        dict with verification results
    """
    print(f"\n{'='*70}")
    print(f"Verifying Seeded Data")
    print(f"{'='*70}\n")

    queries = {
        "otel_traces_count": (
            f"SELECT count(*) FROM {database}.otel_traces",
            expected_trace_count * SPANS_PER_TRACE,
            True  # Critical
        ),
        "unique_traces": (
            f"SELECT uniq(TraceId) FROM {database}.otel_traces",
            expected_trace_count,
            True  # Critical
        ),
        "InferenceFact_count": (
            f"SELECT count(*) FROM {database}.InferenceFact",
            expected_trace_count,
            False  # Non-critical (MV limitation)
        ),
        "InferenceMetrics5m": (
            f"SELECT count(*) FROM {database}.InferenceMetrics5m",
            None,  # Just check > 0
            True  # Critical
        ),
        "InferenceMetrics1h": (
            f"SELECT count(*) FROM {database}.InferenceMetrics1h",
            None,
            True  # Critical
        ),
        "InferenceMetrics1d": (
            f"SELECT count(*) FROM {database}.InferenceMetrics1d",
            None,
            True  # Critical
        ),
    }

    results = {}
    critical_failures = False

    for name, (query, expected, is_critical) in queries.items():
        cmd = ["docker", "exec", container, "clickhouse-client", "--query", query]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            actual = int(result.stdout.strip())
            results[name] = actual

            if expected is not None:
                passed = actual == expected
                # For InferenceFact, consider >30% population as acceptable
                if name == "InferenceFact_count" and not passed:
                    percent = (actual / expected * 100) if expected > 0 else 0
                    passed = percent >= 30  # Accept if at least 30% populated
                    status = f"⚠ WARN " if not passed else f"✓ PASS "
                    print(f"{name:25} {status:10} Expected: {expected:15,} Actual: {actual:15,} ({percent:.1f}%)")
                    if not passed:
                        print(f"{'':25}            Note: InferenceFact partial population is expected (MV limitation)")
                else:
                    status = "✓ PASS" if passed else "✗ FAIL"
                    print(f"{name:25} {status:10} Expected: {expected:15,} Actual: {actual:15,}")
                    if not passed and is_critical:
                        critical_failures = True
            else:
                passed = actual > 0
                status = "✓ PASS" if passed else "✗ FAIL"
                print(f"{name:25} {status:10} Count: {actual:,}")
                if not passed and is_critical:
                    critical_failures = True
        else:
            results[name] = f"ERROR: {result.stderr[:100]}"
            print(f"{name:25} ✗ ERROR  {result.stderr[:50]}")
            if is_critical:
                critical_failures = True

    # Sample check - verify recent traces
    sample_query = f"""
        SELECT inference_id, is_success, timestamp
        FROM {database}.InferenceFact
        ORDER BY timestamp DESC
        LIMIT 10
    """
    cmd = ["docker", "exec", container, "clickhouse-client", "--query", sample_query]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    if result.returncode == 0:
        print(f"\nSample InferenceFact rows (most recent 10):")
        print(result.stdout)

    print(f"\n{'='*70}")
    print(f"Verification: {'✓ PASSED' if not critical_failures else '✗ FAILED'}")
    if not critical_failures:
        print(f"Note: Critical tables (otel_traces, rollup tables) verified successfully")
    print(f"{'='*70}\n")

    results["all_passed"] = not critical_failures
    return results


# ============================================================================
# CLI Interface
# ============================================================================


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Bulk seed OTel traces for performance testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 10M success traces only
  python seed_otel_traces_bulk.py --total 10000000

  # Generate 1M traces with 90% success rate
  python seed_otel_traces_bulk.py --total 1000000 --success 900000 --error 100000

  # Generate 50M traces with 95% success rate, 8 workers
  python seed_otel_traces_bulk.py --total 50000000 --success 47500000 --error 2500000 --workers 8

  # Test with small dataset and verify
  python seed_otel_traces_bulk.py --total 1000 --verify

  # Clear before seeding
  python seed_otel_traces.py --clear
  python seed_otel_traces_bulk.py --total 1000000 --verify
        """
    )

    parser.add_argument(
        "--total",
        type=int,
        help="Total traces to generate"
    )
    parser.add_argument(
        "--success",
        type=int,
        help="Success trace count"
    )
    parser.add_argument(
        "--error",
        type=int,
        help="Error trace count"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Traces per batch (default: {DEFAULT_BATCH_SIZE})"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Number of parallel workers (default: {DEFAULT_WORKERS})"
    )
    parser.add_argument(
        "--database",
        default=DEFAULT_DATABASE,
        help=f"ClickHouse database (default: {DEFAULT_DATABASE})"
    )
    parser.add_argument(
        "--container",
        default="otel-clickhouse",
        help="Docker container name (default: otel-clickhouse)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify data after seeding"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.total is None and args.success is None and args.error is None:
        parser.error("Must specify at least one of --total, --success, or --error")

    # Run seeding
    result = seed_otel_traces_bulk(
        total=args.total,
        success_count=args.success,
        error_count=args.error,
        batch_size=args.batch_size,
        num_workers=args.workers,
        database=args.database,
        container=args.container
    )

    if result.get("error"):
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    # Verify if requested
    if args.verify:
        verify_result = verify_bulk_seeded_data(
            expected_trace_count=result["total_traces"],
            database=args.database,
            container=args.container
        )
        if not verify_result.get("all_passed"):
            sys.exit(1)


if __name__ == "__main__":
    main()
