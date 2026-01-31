"""Fixtures for prompt analytics integration tests.

This module provides shared fixtures for:
- Database connection via docker exec
- Table cleanup between tests
- Seeding otel_traces with test data
- Query helpers for InferenceFact and rollup tables
"""

import json
import time

import pytest

# Import seeding functions from standalone seeder
from tests.prompt_analytics.seed_otel_traces import (
    DEFAULT_CONTAINER,
    DEFAULT_DATABASE,
    clear_tables,
    execute_query,
    load_trace_data,
    seed_otel_traces,
)


# Re-export for convenience
DATABASE = DEFAULT_DATABASE
CONTAINER = DEFAULT_CONTAINER

# Alias for backward compatibility with tests
load_test_data = load_trace_data


def clear_all_tables() -> dict[str, str]:
    """Clear all tables for clean test state.

    Returns:
        Dict mapping table name to status ("cleared" or error message)
    """
    return clear_tables(DATABASE, CONTAINER)


def query_inference_fact(inference_id: str) -> dict | None:
    """Query InferenceFact by inference_id.

    Args:
        inference_id: The inference_id to query

    Returns:
        Dict of row data or None if not found
    """
    result = execute_query(
        f"SELECT * FROM InferenceFact WHERE toString(inference_id) = '{inference_id}'",
        format="JSONEachRow",
        database=DATABASE,
        container=CONTAINER,
    )
    if not result:
        return None
    return json.loads(result.split("\n")[0])


def query_inference_fact_by_trace(trace_id: str) -> list[dict]:
    """Query all InferenceFact rows for a trace.

    Args:
        trace_id: The trace_id to query

    Returns:
        List of row dicts ordered by timestamp
    """
    result = execute_query(
        f"SELECT * FROM InferenceFact WHERE trace_id = '{trace_id}' ORDER BY timestamp",
        format="JSONEachRow",
        database=DATABASE,
        container=CONTAINER,
    )
    if not result:
        return []
    return [json.loads(line) for line in result.split("\n") if line]


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
        format="JSONEachRow",
        database=DATABASE,
        container=CONTAINER,
    )
    if not result:
        return []
    return [json.loads(line) for line in result.split("\n") if line]


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
    return load_trace_data()
