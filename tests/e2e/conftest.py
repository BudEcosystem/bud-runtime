"""
Shared pytest fixtures for E2E tests.

This module provides common fixtures used across all E2E tests, including:
- Service client fixtures (budapp, budcluster, etc.)
- Authentication fixtures
- Infrastructure fixtures (database, redis)
- Test data fixtures
- Cleanup fixtures
"""

import os
import asyncio
from typing import AsyncGenerator, Dict, Any
from uuid import uuid4

import pytest
import httpx
from dotenv import load_dotenv

# Load E2E test environment variables
load_dotenv(".env.e2e")

# Import auth fixtures to make them available
from tests.e2e.fixtures.auth import (
    unique_email,
    strong_password,
    weak_password,
    test_user_data,
    admin_user_credentials,
    registered_user,
    authenticated_user,
    auth_tokens,
    auth_headers,
    AuthTokens,
    TestUser,
)


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def e2e_config() -> Dict[str, Any]:
    """Load E2E test configuration."""
    return {
        # Service URLs (Kind NodePort mappings)
        "budapp_url": os.getenv("E2E_BUDAPP_URL", "http://localhost:9081"),
        # Redis configuration for rate limit clearing
        "redis_url": os.getenv(
            "E2E_REDIS_URL",
            "redis://default:e2e-redis-password@localhost:30379/2"
        ),
        "budcluster_url": os.getenv("E2E_BUDCLUSTER_URL", "http://localhost:9002"),
        "budsim_url": os.getenv("E2E_BUDSIM_URL", "http://localhost:9003"),
        "budmodel_url": os.getenv("E2E_BUDMODEL_URL", "http://localhost:9004"),
        "budmetrics_url": os.getenv("E2E_BUDMETRICS_URL", "http://localhost:9005"),
        "budnotify_url": os.getenv("E2E_BUDNOTIFY_URL", "http://localhost:9006"),
        "budgateway_url": os.getenv("E2E_BUDGATEWAY_URL", "http://localhost:9000"),
        # Database connections
        "postgres_host": os.getenv("E2E_POSTGRES_HOST", "localhost"),
        "postgres_port": int(os.getenv("E2E_POSTGRES_PORT", "9432")),
        "postgres_user": os.getenv("E2E_POSTGRES_USER", "budapp"),
        "postgres_password": os.getenv("E2E_POSTGRES_PASSWORD", "budapp-password"),
        "postgres_db": os.getenv("E2E_POSTGRES_DB", "budapp"),
        "redis_host": os.getenv("E2E_REDIS_HOST", "localhost"),
        "redis_port": int(os.getenv("E2E_REDIS_PORT", "9379")),
        "clickhouse_host": os.getenv("E2E_CLICKHOUSE_HOST", "localhost"),
        "clickhouse_port": int(os.getenv("E2E_CLICKHOUSE_PORT", "9124")),
        "test_timeout": int(os.getenv("E2E_TEST_TIMEOUT", "300")),
    }


# ============================================================================
# Service Client Fixtures
# ============================================================================

@pytest.fixture
async def budapp_client(e2e_config) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create budapp HTTP client."""
    async with httpx.AsyncClient(
        base_url=e2e_config["budapp_url"],
        timeout=httpx.Timeout(30.0)
    ) as client:
        yield client


@pytest.fixture
async def budcluster_client(e2e_config) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create budcluster HTTP client."""
    async with httpx.AsyncClient(
        base_url=e2e_config["budcluster_url"],
        timeout=httpx.Timeout(30.0)
    ) as client:
        yield client


@pytest.fixture
async def budsim_client(e2e_config) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create budsim HTTP client."""
    async with httpx.AsyncClient(
        base_url=e2e_config["budsim_url"],
        timeout=httpx.Timeout(30.0)
    ) as client:
        yield client


@pytest.fixture
async def budmodel_client(e2e_config) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create budmodel HTTP client."""
    async with httpx.AsyncClient(
        base_url=e2e_config["budmodel_url"],
        timeout=httpx.Timeout(30.0)
    ) as client:
        yield client


@pytest.fixture
async def budmetrics_client(e2e_config) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create budmetrics HTTP client."""
    async with httpx.AsyncClient(
        base_url=e2e_config["budmetrics_url"],
        timeout=httpx.Timeout(30.0)
    ) as client:
        yield client


@pytest.fixture
async def budgateway_client(e2e_config) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create budgateway HTTP client."""
    async with httpx.AsyncClient(
        base_url=e2e_config["budgateway_url"],
        timeout=httpx.Timeout(30.0)
    ) as client:
        yield client


# ============================================================================
# Authentication Fixtures
# ============================================================================

@pytest.fixture
async def test_user_credentials() -> Dict[str, str]:
    """Get test user credentials."""
    return {
        "email": os.getenv("E2E_TEST_USER_EMAIL", "test@example.com"),
        "password": os.getenv("E2E_TEST_USER_PASSWORD", "TestPassword123!"),
    }


@pytest.fixture
async def auth_token(budapp_client, test_user_credentials) -> str:
    """
    Get authentication token for test user.

    This fixture attempts to login and returns a valid JWT token.
    If the user doesn't exist, it creates one first.
    """
    # Try to login
    response = await budapp_client.post(
        "/auth/login",
        json=test_user_credentials
    )

    if response.status_code == 200:
        return response.json()["access_token"]

    # User doesn't exist, create one
    create_response = await budapp_client.post(
        "/auth/register",
        json={
            **test_user_credentials,
            "username": f"testuser_{uuid4().hex[:8]}",
            "first_name": "Test",
            "last_name": "User",
        }
    )

    if create_response.status_code not in (200, 201):
        raise AssertionError(f"Failed to create test user: {create_response.text}")

    # Login again
    login_response = await budapp_client.post(
        "/auth/login",
        json=test_user_credentials
    )

    if login_response.status_code != 200:
        raise AssertionError(f"Failed to login: {login_response.text}")

    return login_response.json()["access_token"]


@pytest.fixture
async def auth_headers(auth_token) -> Dict[str, str]:
    """Get authorization headers."""
    return {"Authorization": f"Bearer {auth_token}"}


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
async def test_project(budapp_client, auth_headers) -> Dict[str, Any]:
    """
    Create a test project.

    Yields project data and cleans up after test.
    """
    # Create project
    project_data = {
        "name": f"test-project-{uuid4().hex[:8]}",
        "description": "E2E test project",
        "visibility": "private",
    }

    response = await budapp_client.post(
        "/projects/",
        json=project_data,
        headers=auth_headers
    )

    if response.status_code not in (200, 201):
        raise AssertionError(f"Failed to create project: {response.text}")

    project = response.json()

    yield project

    # Cleanup: Delete project
    try:
        await budapp_client.delete(
            f"/projects/{project['id']}",
            headers=auth_headers
        )
    except Exception as e:
        print(f"Warning: Failed to cleanup project {project['id']}: {e}")


@pytest.fixture
async def test_cluster(budapp_client, auth_headers) -> Dict[str, Any]:
    """
    Create a test cluster.

    Note: This is a placeholder. Actual implementation depends on
    whether you have a test Kubernetes cluster available.

    For now, this returns mock cluster data.
    """
    # TODO: Implement actual cluster creation when test infrastructure is ready
    # For now, return mock data
    cluster = {
        "id": str(uuid4()),
        "name": f"test-cluster-{uuid4().hex[:8]}",
        "status": "ACTIVE",
        "cloud_provider": "azure",
        "region": "eastus",
    }

    yield cluster

    # Cleanup handled by test infrastructure


# ============================================================================
# Infrastructure Fixtures
# ============================================================================

@pytest.fixture
async def postgres_connection(e2e_config):
    """
    Create PostgreSQL connection.

    Use this for direct database queries when needed.
    """
    import asyncpg

    conn = await asyncpg.connect(
        host=e2e_config["postgres_host"],
        port=e2e_config["postgres_port"],
        user=e2e_config["postgres_user"],
        password=e2e_config["postgres_password"],
        database=e2e_config["postgres_db"],
    )

    yield conn

    await conn.close()


@pytest.fixture
async def redis_client(e2e_config):
    """Create Redis client."""
    import redis.asyncio as redis

    client = redis.Redis(
        host=e2e_config["redis_host"],
        port=e2e_config["redis_port"],
        decode_responses=True,
    )

    yield client

    await client.close()


# ============================================================================
# Utility Fixtures
# ============================================================================

@pytest.fixture
def unique_id() -> str:
    """Generate unique ID for test resources."""
    return uuid4().hex[:8]


@pytest.fixture
def test_timeout(e2e_config) -> int:
    """Get default test timeout."""
    return e2e_config["test_timeout"]


# ============================================================================
# Rate Limit Management
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def clear_rate_limits(e2e_config):
    """
    Clear rate limit keys from Redis at the start of test session.

    This is necessary because rate limiting is IP-based and persists
    across test runs. Without clearing, tests may fail due to hitting
    rate limits from previous runs.
    """
    import redis

    redis_url = e2e_config["redis_url"]
    try:
        client = redis.from_url(redis_url)
        # Delete all rate limit keys
        keys = client.keys("rate_limit:*")
        if keys:
            client.delete(*keys)
            print(f"\nCleared {len(keys)} rate limit keys from Redis")
        client.close()
    except Exception as e:
        print(f"\nWarning: Could not clear rate limits: {e}")

    yield

    # Optionally clear again after tests
    try:
        client = redis.from_url(redis_url)
        keys = client.keys("rate_limit:*")
        if keys:
            client.delete(*keys)
        client.close()
    except Exception:
        pass


# ============================================================================
# Hooks
# ============================================================================

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Hook to capture test failures and save debugging information.
    """
    outcome = yield
    rep = outcome.get_result()

    if rep.when == "call" and rep.failed:
        # TODO: Save debugging artifacts
        # - Service logs
        # - Database state
        # - Workflow state
        # - Screenshots (if applicable)
        pass


def pytest_configure(config):
    """Configure pytest."""
    # Create reports directory
    os.makedirs("reports", exist_ok=True)


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to add markers based on test location.
    """
    for item in items:
        # Add e2e marker to all tests in this directory
        item.add_marker(pytest.mark.e2e)

        # Add markers based on directory
        if "workflows" in str(item.fspath):
            item.add_marker(pytest.mark.workflow)
        elif "flows" in str(item.fspath):
            item.add_marker(pytest.mark.flow)
        elif "integrations" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)
