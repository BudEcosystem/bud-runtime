"""Pytest configuration for observability integration tests."""

import subprocess
import sys
from pathlib import Path

import pytest


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )


# Module-level client to ensure single initialization
_test_client = None


@pytest.fixture(scope="session")
def sync_client():
    """Create synchronous test client for API testing.

    Uses FastAPI's TestClient which handles async internally,
    avoiding event loop scope issues with singleton services.

    Important: The client context manager is entered at session start
    and exited at session end to ensure the app's lifespan events
    (startup/shutdown) run exactly once.
    """
    global _test_client

    from fastapi.testclient import TestClient
    from budmetrics.main import app

    # Enter the context manager to trigger app lifespan startup
    _test_client = TestClient(app)
    _test_client.__enter__()

    yield _test_client

    # Exit the context manager to trigger app lifespan shutdown
    _test_client.__exit__(None, None, None)
    _test_client = None


@pytest.fixture(scope="session")
def seed_test_data():
    """Seed OTel test data once for all observability tests.

    This fixture runs the seeder script once per test session,
    ensuring all API tests have consistent test data without
    redundant seeding.
    """
    seeder_path = Path(__file__).parent / "seed_otel_traces.py"
    result = subprocess.run(
        [sys.executable, str(seeder_path), "--clear", "--verify"],
        capture_output=True,
        text=True,
        cwd=str(seeder_path.parent.parent),
    )
    if result.returncode != 0:
        pytest.skip(f"Failed to seed test data: {result.stderr}")
    return True  # Signal that seeding completed
