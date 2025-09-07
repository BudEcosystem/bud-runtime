import os
import sys
import tempfile
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
    # Create secure temporary directory for test keys
    temp_dir = tempfile.mkdtemp(prefix="budapp_test_")
    public_key_path = os.path.join(temp_dir, "test_public_key.pem")
    private_key_path = os.path.join(temp_dir, "test_private_key.pem")

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
        "PUBLIC_KEY_PATH": public_key_path,
        "PRIVATE_KEY_PATH": private_key_path,
        "VAULT_PATH": temp_dir,
        "JWT_SECRET_KEY": "test_jwt_secret_key_for_testing_purposes_only",
        "TENSORZERO_REDIS_URL": "redis://localhost:6379/0",
        "PASSWORD_SALT": "test_salt_for_testing",
        "AES_KEY_HEX": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    }

    # Actually set the environment variables
    for key, value in test_env_vars.items():
        os.environ[key] = value

    # Generate test RSA key pair dynamically to avoid hardcoded keys in source
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        # Generate a new RSA key pair for testing
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Serialize private key with the expected password
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(b"bud_encryption_password")
        )

        # Serialize public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        # Write keys to files
        with open(private_key_path, "wb") as f:
            f.write(private_pem)

        with open(public_key_path, "wb") as f:
            f.write(public_pem)

    except ImportError:
        # Fallback if cryptography is not available - create minimal placeholder files
        with open(public_key_path, "w") as f:
            f.write("# Test public key placeholder\n")
        with open(private_key_path, "w") as f:
            f.write("# Test private key placeholder\n")

    yield

    # Clean up after tests
    for key in test_env_vars.keys():
        os.environ.pop(key, None)

    # Clean up temporary directory and all files
    import shutil
    try:
        shutil.rmtree(temp_dir)
    except (FileNotFoundError, OSError):
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
