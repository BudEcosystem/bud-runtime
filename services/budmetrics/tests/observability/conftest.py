"""Pytest configuration for observability integration tests."""

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
