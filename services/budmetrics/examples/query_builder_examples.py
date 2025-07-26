#!/usr/bin/env python3
"""Examples of using the QueryBuilder directly for advanced use cases.

This script demonstrates how to use the QueryBuilder class to construct
complex ClickHouse queries programmatically.
"""

# Set up environment for imports
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID


sys.path.insert(0, str(Path(__file__).parent.parent))

from budmetrics.observability.models import QueryBuilder


def example_1_basic_query():
    """Example 1: Basic request count query."""
    print("\n=== Example 1: Basic Query ===")

    # Create query builder
    qb = QueryBuilder(performance_metrics=None)

    # Build query
    query, fields = qb.build_query(
        metrics=["request_count"],
        from_date=datetime(2024, 1, 1, tzinfo=UTC),
        to_date=datetime(2024, 1, 31, tzinfo=UTC),
        frequency_unit="day",
    )

    print("Query:")
    print(query)
    print(f"\nField order: {fields}")


def example_2_multiple_metrics_with_grouping():
    """Example 2: Multiple metrics with grouping and filtering."""
    print("\n=== Example 2: Multiple Metrics with Grouping ===")

    qb = QueryBuilder(performance_metrics=None)

    query, fields = qb.build_query(
        metrics=["request_count", "latency", "success_request"],
        from_date=datetime(2024, 1, 1, tzinfo=UTC),
        to_date=datetime(2024, 1, 7, tzinfo=UTC),
        frequency_unit="hour",
        group_by=["project", "model"],
        filters={
            "project": [UUID("550e8400-e29b-41d4-a716-446655440000"), UUID("550e8400-e29b-41d4-a716-446655440001")]
        },
        return_delta=True,
    )

    print("Query with grouping and filters:")
    print(query)
    print(f"\nFields: {fields}")


def example_3_topk_query():
    """Example 3: TopK query to get top entities."""
    print("\n=== Example 3: TopK Query ===")

    qb = QueryBuilder(performance_metrics=None)

    query, fields = qb.build_query(
        metrics=["request_count", "latency"],
        from_date=datetime(2024, 1, 1, tzinfo=UTC),
        to_date=datetime(2024, 1, 31, tzinfo=UTC),
        frequency_unit="week",
        group_by=["model"],
        topk=10,  # Top 10 models by request count
        return_delta=True,
    )

    print("TopK Query (Top 10 models):")
    print(query)


def example_4_concurrent_requests():
    """Example 4: Concurrent requests with CTE."""
    print("\n=== Example 4: Concurrent Requests ===")

    qb = QueryBuilder(performance_metrics=None)

    query, fields = qb.build_query(
        metrics=["concurrent_requests"],
        from_date=datetime.now(UTC) - timedelta(days=1),
        to_date=datetime.now(UTC),
        frequency_unit="hour",
        group_by=["project"],
        fill_time_gaps=True,
    )

    print("Concurrent Requests Query (with CTE):")
    print(query)


def example_5_custom_intervals():
    """Example 5: Custom time intervals with alignment."""
    print("\n=== Example 5: Custom Intervals ===")

    qb = QueryBuilder(performance_metrics=None)

    # 7-day intervals starting from specific date
    from_date = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    query1, _ = qb.build_query(
        metrics=["request_count"],
        from_date=from_date,
        to_date=from_date + timedelta(days=28),
        frequency_unit="day",
        frequency_interval=7,  # Custom 7-day intervals
        fill_time_gaps=False,
    )

    print("Custom 7-day intervals (aligned to from_date):")
    print(query1)

    # Standard daily intervals for comparison
    query2, _ = qb.build_query(
        metrics=["request_count"],
        from_date=from_date,
        to_date=from_date + timedelta(days=28),
        frequency_unit="day",
        frequency_interval=None,  # Standard daily
        fill_time_gaps=False,
    )

    print("\nStandard daily intervals (calendar-based):")
    print(query2)


def example_6_performance_metrics():
    """Example 6: Performance metrics with percentiles."""
    print("\n=== Example 6: Performance Metrics ===")

    qb = QueryBuilder(performance_metrics=None)

    query, fields = qb.build_query(
        metrics=["latency", "ttft", "throughput"],
        from_date=datetime.now(UTC) - timedelta(hours=24),
        to_date=datetime.now(UTC),
        frequency_unit="hour",
        group_by=["endpoint"],
        topk=5,
    )

    print("Performance metrics query (includes percentiles):")
    print(query)
    print(f"\nMetric fields: {[f for f in fields if f not in ['time_bucket', 'endpoint']]}")


def example_7_token_metrics():
    """Example 7: Token metrics for cost analysis."""
    print("\n=== Example 7: Token Metrics ===")

    qb = QueryBuilder(performance_metrics=None)

    query, fields = qb.build_query(
        metrics=["input_token", "output_token"],
        from_date=datetime(2024, 1, 1, tzinfo=UTC),
        to_date=datetime(2024, 1, 31, tzinfo=UTC),
        frequency_unit="day",
        group_by=["project", "model"],
        return_delta=True,
        topk=20,
    )

    print("Token usage query with deltas:")
    print(query)


def example_8_cache_metrics():
    """Example 8: Cache performance metrics."""
    print("\n=== Example 8: Cache Metrics ===")

    qb = QueryBuilder(performance_metrics=None)

    query, fields = qb.build_query(
        metrics=["cache"],
        from_date=datetime.now(UTC) - timedelta(days=7),
        frequency_unit="day",
        group_by=["model"],
        return_delta=False,
    )

    print("Cache metrics query:")
    print(query)
    print(f"\nCache fields: {[f for f in fields if 'cache' in f]}")


def example_9_complex_filtering():
    """Example 9: Complex filtering with multiple conditions."""
    print("\n=== Example 9: Complex Filtering ===")

    qb = QueryBuilder(performance_metrics=None)

    # Multiple filters
    filters = {
        "project": UUID("550e8400-e29b-41d4-a716-446655440000"),  # Single project
        "model": [
            UUID("650e8400-e29b-41d4-a716-446655440001"),
            UUID("650e8400-e29b-41d4-a716-446655440002"),
            UUID("650e8400-e29b-41d4-a716-446655440003"),
        ],  # Multiple models
        "endpoint": UUID("750e8400-e29b-41d4-a716-446655440000"),  # Single endpoint
    }

    query, fields = qb.build_query(
        metrics=["request_count", "success_request", "failure_request"],
        from_date=datetime.now(UTC) - timedelta(days=1),
        frequency_unit="hour",
        filters=filters,
        return_delta=True,
    )

    print("Query with complex filters:")
    print(query)


def example_10_all_metrics():
    """Example 10: Query with all available metrics."""
    print("\n=== Example 10: All Metrics ===")

    qb = QueryBuilder(performance_metrics=None)

    all_metrics = [
        "request_count",
        "success_request",
        "failure_request",
        "queuing_time",
        "input_token",
        "output_token",
        "concurrent_requests",
        "ttft",
        "latency",
        "throughput",
        "cache",
    ]

    query, fields = qb.build_query(
        metrics=all_metrics, from_date=datetime.now(UTC) - timedelta(hours=1), frequency_unit="hour"
    )

    print(f"Query with all {len(all_metrics)} metrics:")
    print("Fields generated:")
    for i, field in enumerate(fields):
        print(f"  {i + 1}. {field}")

    print(f"\nTotal fields: {len(fields)}")


def main():
    """Run all examples."""
    examples = [
        example_1_basic_query,
        example_2_multiple_metrics_with_grouping,
        example_3_topk_query,
        example_4_concurrent_requests,
        example_5_custom_intervals,
        example_6_performance_metrics,
        example_7_token_metrics,
        example_8_cache_metrics,
        example_9_complex_filtering,
        example_10_all_metrics,
    ]

    print("QueryBuilder Examples")
    print("====================")
    print("These examples show the SQL queries generated by QueryBuilder")

    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"\nError in {example.__name__}: {e}")


if __name__ == "__main__":
    main()
