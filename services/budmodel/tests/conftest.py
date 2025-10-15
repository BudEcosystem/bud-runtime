import os
import sys
from typing import Any

import pytest

# Set required environment variables for tests before importing app modules
os.environ.setdefault("PSQL_HOST", "localhost")
os.environ.setdefault("PSQL_PORT", "5432")
os.environ.setdefault("PSQL_DB_NAME", "test_db")
os.environ.setdefault("PSQL_USER", "test_user")
os.environ.setdefault("PSQL_PASSWORD", "test_password")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("BUDCONNECT_URL", "https://budconnect.bud.studio/")

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
