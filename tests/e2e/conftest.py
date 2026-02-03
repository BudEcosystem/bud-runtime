"""
Shared pytest fixtures for E2E tests.

This module provides common fixtures used across all E2E tests, including:
- Service client fixtures (budapp, budcluster, etc.)
- Authentication fixtures
- Infrastructure fixtures (database, redis)
- Test data fixtures
- Cleanup fixtures
- Test session isolation
"""

import os
import logging
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, Optional
from uuid import uuid4

import pytest
import httpx
from dotenv import load_dotenv

# Load E2E test environment variables
load_dotenv(".env.e2e")

# Import core infrastructure (after load_dotenv to ensure env vars are available)
from tests.e2e.core.config import TimeoutConfig, get_config  # noqa: E402
from tests.e2e.core.waiter import WorkflowWaiter  # noqa: E402
from tests.e2e.core.retry import RetryConfig, RetryContext  # noqa: E402

# Import auth fixtures to make them available to tests
from tests.e2e.fixtures.auth import (  # noqa: E402, F401, F811
    unique_email,
    strong_password,
    weak_password,
    test_user_data,
    admin_user_credentials,
    registered_user,
    authenticated_user,
    authenticated_admin_user,
    auth_tokens,
    auth_headers,
    AuthTokens,
    TestUser,
    AdminUser,
)

# Import model fixtures to make them available to tests
from tests.e2e.fixtures.models import (  # noqa: E402, F401
    unique_model_name,
    model_tags,
    cloud_model_provider,
    available_cloud_model,
    created_model,
    model_list,
    generate_unique_model_name,
    generate_model_tags,
    TestModel,
    ModelProviderType,
    WorkflowStatus,
    Provider,
)

# Configure logging for E2E tests
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("e2e")


# ============================================================================
# Test Session Isolation
# ============================================================================

# Global test session state
_test_session: Optional[Dict[str, Any]] = None


@pytest.fixture(scope="session")
def test_session_id() -> str:
    """
    Generate a unique test session ID.

    This ID is used to isolate test resources created during this test run
    from resources created by other test runs (e.g., parallel CI jobs).
    """
    session_id = os.getenv("E2E_TEST_SESSION_ID")
    if not session_id:
        # Generate a unique session ID based on timestamp and random component
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        random_suffix = uuid4().hex[:6]
        session_id = f"{timestamp}-{random_suffix}"

    logger.info(f"Test session ID: {session_id}")
    return session_id


@pytest.fixture(scope="session")
def test_resource_prefix(test_session_id) -> str:
    """
    Get prefix for test resources.

    All test resources (projects, models, etc.) should be named with this
    prefix to enable easy identification and cleanup.
    """
    base_prefix = os.getenv("E2E_TEST_PROJECT_PREFIX", "e2e-test")
    return f"{base_prefix}-{test_session_id}"


@pytest.fixture(scope="session")
def test_session(test_session_id, test_resource_prefix) -> Dict[str, Any]:
    """
    Initialize test session state.

    This fixture tracks all resources created during the test session
    for cleanup purposes.
    """
    global _test_session

    _test_session = {
        "session_id": test_session_id,
        "resource_prefix": test_resource_prefix,
        "started_at": datetime.now().isoformat(),
        "created_resources": {
            "projects": [],
            "models": [],
            "clusters": [],
            "endpoints": [],
            "users": [],
        },
    }

    logger.info(f"Test session initialized: {test_session_id}")
    yield _test_session

    # Log session summary
    logger.info(f"Test session completed: {test_session_id}")
    for resource_type, resources in _test_session["created_resources"].items():
        if resources:
            logger.info(f"  {resource_type}: {len(resources)} created")


def register_test_resource(resource_type: str, resource_id: str) -> None:
    """
    Register a created resource for tracking.

    Args:
        resource_type: Type of resource (projects, models, clusters, etc.)
        resource_id: ID of the created resource
    """
    global _test_session
    if _test_session and resource_type in _test_session["created_resources"]:
        _test_session["created_resources"][resource_type].append(resource_id)


# ============================================================================
# Configuration Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def e2e_config() -> Dict[str, Any]:
    """Load E2E test configuration."""
    # Use the new config system
    config = get_config()

    # Return dict for backwards compatibility
    return {
        # Service URLs (Kind NodePort mappings)
        "budapp_url": config.budapp_url,
        # Redis configuration for rate limit clearing
        "redis_url": config.redis_url,
        "budcluster_url": os.getenv("E2E_BUDCLUSTER_URL", "http://localhost:9002"),
        "budsim_url": os.getenv("E2E_BUDSIM_URL", "http://localhost:9003"),
        "budmodel_url": os.getenv("E2E_BUDMODEL_URL", "http://localhost:9004"),
        "budmetrics_url": os.getenv("E2E_BUDMETRICS_URL", "http://localhost:9005"),
        "budnotify_url": os.getenv("E2E_BUDNOTIFY_URL", "http://localhost:9006"),
        "budgateway_url": os.getenv("E2E_BUDGATEWAY_URL", "http://localhost:9000"),
        # Database connections
        "postgres_host": config.postgres_host,
        "postgres_port": config.postgres_port,
        "postgres_user": config.postgres_user,
        "postgres_password": config.postgres_password,
        "postgres_db": config.postgres_db,
        "redis_host": config.redis_host,
        "redis_port": config.redis_port,
        "clickhouse_host": os.getenv("E2E_CLICKHOUSE_HOST", "localhost"),
        "clickhouse_port": int(os.getenv("E2E_CLICKHOUSE_PORT", "9124")),
        "test_timeout": config.timeouts.model_local_workflow,
        # Timeouts from new config
        "timeouts": config.timeouts,
    }


@pytest.fixture(scope="session")
def timeout_config() -> TimeoutConfig:
    """Get timeout configuration."""
    return get_config().timeouts


# ============================================================================
# Service Client Fixtures
# ============================================================================


@pytest.fixture
async def budapp_client(e2e_config) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create budapp HTTP client."""
    async with httpx.AsyncClient(
        base_url=e2e_config["budapp_url"], timeout=httpx.Timeout(30.0)
    ) as client:
        yield client


@pytest.fixture
async def budcluster_client(e2e_config) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create budcluster HTTP client."""
    async with httpx.AsyncClient(
        base_url=e2e_config["budcluster_url"], timeout=httpx.Timeout(30.0)
    ) as client:
        yield client


@pytest.fixture
async def budsim_client(e2e_config) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create budsim HTTP client."""
    async with httpx.AsyncClient(
        base_url=e2e_config["budsim_url"], timeout=httpx.Timeout(30.0)
    ) as client:
        yield client


@pytest.fixture
async def budmodel_client(e2e_config) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create budmodel HTTP client."""
    async with httpx.AsyncClient(
        base_url=e2e_config["budmodel_url"], timeout=httpx.Timeout(30.0)
    ) as client:
        yield client


@pytest.fixture
async def budmetrics_client(e2e_config) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create budmetrics HTTP client."""
    async with httpx.AsyncClient(
        base_url=e2e_config["budmetrics_url"], timeout=httpx.Timeout(30.0)
    ) as client:
        yield client


@pytest.fixture
async def budgateway_client(e2e_config) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create budgateway HTTP client."""
    async with httpx.AsyncClient(
        base_url=e2e_config["budgateway_url"], timeout=httpx.Timeout(30.0)
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
    response = await budapp_client.post("/auth/login", json=test_user_credentials)

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
        },
    )

    if create_response.status_code not in (200, 201):
        raise AssertionError(f"Failed to create test user: {create_response.text}")

    # Login again
    login_response = await budapp_client.post("/auth/login", json=test_user_credentials)

    if login_response.status_code != 200:
        raise AssertionError(f"Failed to login: {login_response.text}")

    return login_response.json()["access_token"]


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
async def test_project(budapp_client, auth_headers) -> Dict[str, Any]:  # noqa: F811
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
        "/projects/", json=project_data, headers=auth_headers
    )

    if response.status_code not in (200, 201):
        raise AssertionError(f"Failed to create project: {response.text}")

    project = response.json()

    yield project

    # Cleanup: Delete project
    try:
        await budapp_client.delete(f"/projects/{project['id']}", headers=auth_headers)
    except Exception as e:
        print(f"Warning: Failed to cleanup project {project['id']}: {e}")


@pytest.fixture
async def test_cluster(budapp_client, auth_headers) -> Dict[str, Any]:  # noqa: F811
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
            # Add sub-markers for flow types
            if "auth" in str(item.fspath):
                item.add_marker(pytest.mark.auth)
            elif "models" in str(item.fspath):
                item.add_marker(pytest.mark.models)
        elif "integrations" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)


# ============================================================================
# Workflow Fixtures
# ============================================================================


@pytest.fixture
def workflow_waiter_factory(timeout_config):
    """
    Factory fixture for creating workflow waiters.

    Usage:
        async def test_something(workflow_waiter_factory):
            waiter = workflow_waiter_factory(
                check_func=lambda: api.get_status(id),
                workflow_type="model",
                timeout=600,
            )
            result = await waiter.wait()
    """
    from tests.e2e.core.waiter import WaiterConfig

    def factory(
        check_func,
        workflow_id: Optional[str] = None,
        workflow_type: str = "workflow",
        timeout: Optional[int] = None,
        poll_interval: Optional[int] = None,
    ) -> WorkflowWaiter:
        config = WaiterConfig(
            timeout=timeout or timeout_config.model_local_workflow,
            poll_interval=poll_interval or timeout_config.poll_interval,
        )
        return WorkflowWaiter(
            check_func=check_func,
            config=config,
            workflow_id=workflow_id,
            workflow_type=workflow_type,
        )

    return factory


@pytest.fixture
def retry_context_factory():
    """
    Factory fixture for creating retry contexts.

    Usage:
        async def test_something(retry_context_factory):
            async with retry_context_factory(max_attempts=5) as ctx:
                while ctx.should_continue():
                    try:
                        result = await api_call()
                        ctx.success()
                        break
                    except TransientError as e:
                        await ctx.handle_failure(e)
    """

    def factory(
        max_attempts: int = 3,
        base_delay: float = 1.0,
    ) -> RetryContext:
        config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
        )
        return RetryContext(config=config)

    return factory


# ============================================================================
# Cleanup Fixtures
# ============================================================================


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_resources(test_session, e2e_config):
    """
    Cleanup all test resources created during the session.

    This runs at the end of the test session and attempts to clean up
    any resources that were registered during tests.
    """
    yield

    # Skip cleanup if disabled
    if os.getenv("E2E_SKIP_CLEANUP", "false").lower() in ("true", "1", "yes"):
        logger.info("Skipping resource cleanup (E2E_SKIP_CLEANUP=true)")
        return

    logger.info("Cleaning up test resources...")

    # Use synchronous httpx for session-scoped cleanup
    with httpx.Client(
        base_url=e2e_config["budapp_url"],
        timeout=httpx.Timeout(30.0),
    ) as client:
        # Get admin token for cleanup
        try:
            admin_email = os.getenv("E2E_ADMIN_USER_EMAIL", "admin@bud.studio")
            admin_password = os.getenv("E2E_ADMIN_USER_PASSWORD", "admin-password")

            login_response = client.post(
                "/auth/login",
                json={"email": admin_email, "password": admin_password},
            )

            if login_response.status_code != 200:
                logger.warning("Could not get admin token for cleanup")
                return

            token_data = login_response.json()
            token = token_data.get("token", token_data).get("access_token")
            headers = {"Authorization": f"Bearer {token}"}

            # Cleanup models
            for model_id in test_session["created_resources"].get("models", []):
                try:
                    client.delete(f"/models/{model_id}", headers=headers)
                    logger.debug(f"Deleted model: {model_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete model {model_id}: {e}")

            # Cleanup projects
            for project_id in test_session["created_resources"].get("projects", []):
                try:
                    client.delete(f"/projects/{project_id}", headers=headers)
                    logger.debug(f"Deleted project: {project_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete project {project_id}: {e}")

        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
