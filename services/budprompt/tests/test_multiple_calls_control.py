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

"""Tests for multiple LLM calls control functionality."""

from typing import Any, Dict

import httpx
import pytest
from pydantic import BaseModel


class TestMultipleCallsControl:
    """Tests for allow_multiple_calls and enable_tools configuration."""

    base_url = "http://localhost:9088"
    deployment_name = "qwen3-4b"

    @pytest.fixture
    def http_client(self):
        """Create HTTP client for tests."""
        with httpx.Client(base_url=self.base_url, timeout=120.0) as client:
            yield client

    def _execute_prompt(self, client: httpx.Client, request_data: Dict[str, Any]) -> httpx.Response:
        """Execute prompt and return response."""
        response = client.post("/prompt/execute", json=request_data, headers={"Content-Type": "application/json"})
        return response

    def test_default_allow_multiple_calls(self, http_client):
        """Test that allow_multiple_calls defaults to true."""

        class OutputSchema(BaseModel):
            content: str

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Say hello"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            # Not specifying allow_multiple_calls - should default to true
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

    def test_allow_multiple_calls_false_simple_request(self, http_client):
        """Test that allow_multiple_calls=false works for simple requests."""

        class OutputSchema(BaseModel):
            content: str

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Say hello"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "allow_multiple_calls": False,
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        assert isinstance(result["data"], str)

    def test_allow_multiple_calls_false_with_validation(self, http_client):
        """Test that validation fails immediately with allow_multiple_calls=false (no retries)."""

        class Person(BaseModel):
            name: str
            age: int

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person with name 'John' and age 25"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "output_validation_prompt": "The person's name must be exactly 'Alice'",  # Will fail
            "allow_multiple_calls": False,  # No retries allowed
        }

        response = self._execute_prompt(http_client, request_data)
        # Should fail without retries
        assert response.status_code == 500  # Validation will fail and no retries allowed

    def test_allow_multiple_calls_true_with_validation(self, http_client):
        """Test that validation can retry with allow_multiple_calls=true."""

        class Person(BaseModel):
            name: str
            age: int

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person with name 'Alice' and age 30"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "output_validation_prompt": "The person's age must be exactly 30",
            "allow_multiple_calls": True,  # Retries allowed
            "llm_retry_limit": 3,
        }

        response = self._execute_prompt(http_client, request_data)
        # Should succeed with retries if needed
        assert response.status_code == 200

    def test_enable_tools_true_requires_multiple_calls(self, http_client):
        """Test that enable_tools=true with allow_multiple_calls=false raises error."""

        class OutputSchema(BaseModel):
            content: str

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Say hello"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "enable_tools": True,
            "allow_multiple_calls": False,  # Invalid combination
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 400

        result = response.json()
        assert "message" in result
        assert "tools requires multiple" in result["message"].lower()

    def test_enable_tools_true_with_multiple_calls(self, http_client):
        """Test that enable_tools=true with allow_multiple_calls=true is accepted."""

        class OutputSchema(BaseModel):
            content: str

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Say hello"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "enable_tools": True,
            "allow_multiple_calls": True,  # Valid combination
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

    def test_enable_tools_false_allows_either_multiple_calls_setting(self, http_client):
        """Test that enable_tools=false works with any allow_multiple_calls setting."""

        class OutputSchema(BaseModel):
            content: str

        # Test with allow_multiple_calls=false
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Say hello"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "enable_tools": False,
            "allow_multiple_calls": False,
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        # Test with allow_multiple_calls=true
        request_data["allow_multiple_calls"] = True

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

    def test_input_validation_with_allow_multiple_calls_false(self, http_client):
        """Test input validation with allow_multiple_calls=false."""

        class Person(BaseModel):
            name: str
            age: int

        class InputSchema(BaseModel):
            content: Person

        class OutputSchema(BaseModel):
            content: str

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Describe this person"},
            ],
            "input_schema": InputSchema.model_json_schema(),
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": {"content": {"name": "John", "age": 16}},
            "input_validation_prompt": "Age must be greater than 18",
            "allow_multiple_calls": False,
        }

        response = self._execute_prompt(http_client, request_data)
        # Input validation happens before LLM call, so should still fail with 422
        assert response.status_code == 422

    def test_complex_scenario_validation_and_multiple_calls(self, http_client):
        """Test complex scenario with both input/output validation and multiple calls control."""

        class Person(BaseModel):
            name: str
            age: int
            city: str

        class InputSchema(BaseModel):
            content: Person

        class OutputPerson(BaseModel):
            name: str
            age: int
            description: str

        class OutputSchema(BaseModel):
            content: OutputPerson

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Create a description for this person and return their details"},
            ],
            "input_schema": InputSchema.model_json_schema(),
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": {"content": {"name": "Alice", "age": 30, "city": "New York"}},
            "input_validation_prompt": "Age must be greater than 25",
            "output_validation_prompt": "Description must be at least 10 characters long",
            "allow_multiple_calls": False,  # No retries for output validation
            "llm_retry_limit": 3,  # This will be overridden to 0
        }

        response = self._execute_prompt(http_client, request_data)
        # May succeed or fail depending on first LLM output (no retries)
        assert response.status_code in [200, 500]


# docker exec budserve-development-budprompt pytest tests/test_multiple_calls_control.py -v
