import os
import sys
from typing import Any, Union

import pytest

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
