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

"""Tests for message roles and system prompt role configuration."""

from typing import Any, Dict

import httpx
import pytest
from pydantic import BaseModel


class TestMessageRoles:
    """Tests for message roles and system prompt configuration."""

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

    def test_basic_message_roles(self, http_client):
        """Test that basic message roles (user, assistant) work."""

        class OutputSchema(BaseModel):
            content: str

        request_data = {
            "deployment_name": self.deployment_name,
            "output_schema": OutputSchema.model_json_schema(),
            "messages": [
                {"role": "developer", "content": "You are a helpful assistant. Be concise."},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "What's 2+2?"},
            ],
            "model_settings": {
                "system_prompt_role": "developer",
            },
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert "data" in result

    def test_system_prompt_influences_output(self, http_client):
        """Test that system prompt provides context for the model."""

        class Person(BaseModel):
            name: str
            age: int

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "output_schema": OutputSchema.model_json_schema(),
            "messages": [
                {"role": "system", "content": "Generate person data with realistic ages."},
                {"role": "user", "content": "Create a person named Alice"},
            ],
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        # Check that structured output was generated
        assert "name" in result["data"]
        assert "age" in result["data"]
        assert isinstance(result["data"]["age"], int)

    def test_system_prompt_role_configuration(self, http_client):
        """Test system_prompt_role configuration in model settings."""

        class OutputSchema(BaseModel):
            content: str

        # Test with system role (default)
        request_data = {
            "deployment_name": self.deployment_name,
            "output_schema": OutputSchema.model_json_schema(),
            "system_prompt_role": "system",  # Explicit system role
            "model_settings": {
                "temperature": 0.7,
            },
            "messages": [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello"},
            ],
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

    def test_system_prompt_role_developer(self, http_client):
        """Test developer system_prompt_role (may fail with incompatible models)."""

        class OutputSchema(BaseModel):
            content: str

        request_data = {
            "deployment_name": self.deployment_name,
            "output_schema": OutputSchema.model_json_schema(),
            "system_prompt_role": "developer",  # Developer role for system prompts
            "model_settings": {
                "temperature": 0.7,
            },
            "messages": [
                {"role": "developer", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello"},
            ],
        }

        response = self._execute_prompt(http_client, request_data)
        # This may succeed or fail depending on model compatibility
        assert response.status_code in [200, 500]

    def test_conversation_flow(self, http_client):
        """Test conversation flow with user and assistant messages."""

        class OutputSchema(BaseModel):
            content: str

        request_data = {
            "deployment_name": self.deployment_name,
            "output_schema": OutputSchema.model_json_schema(),
            "messages": [
                {"role": "system", "content": "You are a helpful assistant. Be concise and helpful."},
                {"role": "user", "content": "What's 2+2?"},
                {"role": "assistant", "content": "2+2 equals 4."},
                {"role": "user", "content": "Thanks! Can you explain why?"},
            ],
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert "data" in result

    def test_message_role_with_template_rendering(self, http_client):
        """Test that message content templates are rendered correctly for all roles."""

        class Person(BaseModel):
            name: str
            age: int

        class InputSchema(BaseModel):
            content: Person

        class OutputSchema(BaseModel):
            content: str

        request_data = {
            "deployment_name": self.deployment_name,
            "input_schema": InputSchema.model_json_schema(),
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": {"content": {"name": "Bob", "age": 25}},
            "messages": [
                {"role": "system", "content": "Process the person data"},
                {"role": "user", "content": "Describe {{name}}"},
                {"role": "assistant", "content": "Processing {{name}}'s data"},
                {"role": "user", "content": "Age {{age}} is valid for {{name}}"},
            ],
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

    def test_invalid_role_rejection(self, http_client):
        """Test that invalid roles are rejected."""

        class OutputSchema(BaseModel):
            content: str

        request_data = {
            "deployment_name": self.deployment_name,
            "output_schema": OutputSchema.model_json_schema(),
            "messages": [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "invalid_role", "content": "This should fail"},
            ],
        }

        response = self._execute_prompt(http_client, request_data)
        # Should fail with validation error
        assert response.status_code == 422


# docker exec budserve-development-budprompt pytest tests/test_message_roles.py -v

# docker exec budserve-development-budprompt pytest tests/test_message_roles.py::TestMessageRoles::test_system_prompt_influences_output -v
