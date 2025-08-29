#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Tests for the health endpoint."""

import os
import pytest
import httpx


# Get the app port from environment variable or use default
APP_PORT = os.getenv("APP_PORT", "9088")
BASE_URL = f"http://localhost:{APP_PORT}"


@pytest.fixture
def http_client():
    """Create an HTTP client for making requests."""
    with httpx.Client(base_url=BASE_URL) as client:
        yield client


def test_health_endpoint(http_client):
    """Test the /health endpoint returns expected response."""
    response = http_client.get("/health", headers={"accept": "application/json"})
    
    assert response.status_code == 200
    
    json_response = response.json()
    assert json_response == {
        "object": "info",
        "message": "ack",
        "param": None
    }


def test_health_endpoint_content_type(http_client):
    """Test the /health endpoint returns JSON content type."""
    response = http_client.get("/health", headers={"accept": "application/json"})
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"


# Command to run the tests
# docker exec -it budserve-development-budprompt pytest tests/test_health.py -v