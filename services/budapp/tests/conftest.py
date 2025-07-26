import os
import sys
from typing import Any

import pytest
from unittest import mock

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
        "SUPER_USER_EMAIL": "test@example.com",
        "SUPER_USER_PASSWORD": "test_super_password",
        "DAPR_BASE_URL": "http://localhost:3500",
        "BUD_CLUSTER_APP_ID": "cluster-app",
        "BUD_MODEL_APP_ID": "model-app",
        "BUD_SIMULATOR_APP_ID": "simulator-app",
        "BUD_METRICS_APP_ID": "metrics-app",
        "BUD_NOTIFY_APP_ID": "notify-app"
    }

    # Actually set the environment variables
    for key, value in test_env_vars.items():
        os.environ[key] = value

    yield

    # Clean up after tests
    for key in test_env_vars.keys():
        os.environ.pop(key, None)
