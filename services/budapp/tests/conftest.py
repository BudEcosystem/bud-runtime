import os
import sys
from typing import Any, AsyncGenerator

import pytest
from unittest import mock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--dapr-http-port", action="store", default=3510, type=int, help="Dapr HTTP port")
    parser.addoption("--dapr-api-token", action="store", default=None, type=str, help="Dapr API token")


@pytest.fixture(scope="session")
def dapr_http_port(request: pytest.FixtureRequest) -> Any:
    arg_value = request.config.getoption("--dapr-http-port")
    if arg_value is None:
        pytest.fail("--dapr-http-port is required to run the tests")
    return arg_value


@pytest.fixture(scope="session")
def dapr_api_token(request: pytest.FixtureRequest) -> Any:
    return request.config.getoption("--dapr-api-token")


@pytest.fixture(scope="session", autouse=True)
def mock_env_vars():
    test_env_vars = {
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test_password",
        "POSTGRES_DB": "test_db",
        "PSQL_HOST": "localhost",
        "PSQL_PORT": "5432",
        "PSQL_DB_NAME": "test_db",
        "SUPER_USER_EMAIL": "test@example.com",
        "SUPER_USER_PASSWORD": "test_super_password",
        "DAPR_BASE_URL": "http://localhost:3500",
        "BUD_CLUSTER_APP_ID": "cluster-app",
        "BUD_MODEL_APP_ID": "model-app",
        "BUD_SIMULATOR_APP_ID": "simulator-app",
        "BUD_METRICS_APP_ID": "metrics-app",
        "BUD_NOTIFY_APP_ID": "notify-app",
        "KEYCLOAK_SERVER_URL": "http://localhost:8080",
        "KEYCLOAK_ADMIN_USERNAME": "admin",
        "KEYCLOAK_ADMIN_PASSWORD": "admin",
        "KEYCLOAK_REALM_NAME": "test-realm",
        "GRAFANA_SCHEME": "http",
        "GRAFANA_URL": "localhost:3000",
        "GRAFANA_USERNAME": "admin",
        "GRAFANA_PASSWORD": "admin",
        "CLOUD_MODEL_SEEDER_ENGINE": "openai",
        "BUD_CONNECT_BASE_URL": "http://localhost:8001",
        "PUBLIC_KEY_PATH": "/tmp/test_public_key.pem",
        "PRIVATE_KEY_PATH": "/tmp/test_private_key.pem",
        "VAULT_PATH": "/tmp"
    }

    # Actually set the environment variables
    for key, value in test_env_vars.items():
        os.environ[key] = value

    # Create test key files for RSA handler
    public_key_content = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA77W82GAHTupjewJ4Df7Q
+crGYVN1SsIQp1j/3PAGIdcUb2Aw2796HHecuOpPjp5coXopIqUapwqeFYr8PG3e
pbY7iplt9QNnyZDgDuoBfvz2hJJtTacsBKm+XUr35WqKW8l/NeGwAAZwSlw6fu7f
3k/ga7GrXo/7AYl43vuEZ+NyiEzAGaACsoEIY9MvB472zOE9R1utYD+bK8RFGypO
G+7FbqNImu3JSCBNLzHLYr17Mg8/bJeugx/FMvkNi+7c48hf5m2gzXGSFLxPK6k/
ioehgykSlgApkssHLTkZpW47nKT4vU0D/e10o9XnPUnte6keW4/5KIU88Rr+8K1t
IQIDAQAB
-----END PUBLIC KEY-----"""

    with open("/tmp/test_public_key.pem", "w") as f:
        f.write(public_key_content)

    yield

    # Clean up after tests
    for key in test_env_vars.keys():
        os.environ.pop(key, None)

    # Clean up key files
    try:
        os.remove("/tmp/test_public_key.pem")
    except FileNotFoundError:
        pass


@pytest.fixture
async def async_session():
    """Create a mock async database session for testing."""
    from unittest.mock import AsyncMock, Mock

    session = AsyncMock(spec=AsyncSession)
    session.add = Mock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    return session


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    # Import here to avoid circular imports and ensure env vars are set
    from budapp.main import app

    with TestClient(app) as test_client:
        yield test_client
