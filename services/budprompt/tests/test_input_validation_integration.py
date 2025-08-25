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

"""Integration tests for input validation functionality with actual API calls."""

from typing import Any, Dict

import httpx
import pytest
from pydantic import BaseModel


class TestInputValidationIntegration:
    """Integration tests for input validation using actual API calls."""

    base_url = "http://localhost:9088"
    deployment_name = "qwen3-32b"

    @pytest.fixture
    def http_client(self):
        """Create HTTP client for tests."""
        with httpx.Client(base_url=self.base_url, timeout=120.0) as client:
            yield client

    def _execute_prompt(self, client: httpx.Client, request_data: Dict[str, Any]) -> httpx.Response:
        """Execute prompt and return response."""
        response = client.post("/prompt/execute", json=request_data, headers={"Content-Type": "application/json"})
        return response

    @pytest.mark.timeout(180)
    def test_input_validation_disabled_simple_input(self, http_client):
        """Test that validation is not applied when no input validation prompt is provided."""

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
                {"role": "system", "content": "Describe the person briefly"},
            ],
            "input_schema": InputSchema.model_json_schema(),
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": {"name": "John", "age": 25},
            # No input_validation_prompt - validation should be disabled
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        assert isinstance(result["data"], str)
        assert len(result["data"]) > 0

    def test_input_validation_simple_success(self, http_client):
        """Test simple input validation that should succeed."""

        class Person(BaseModel):
            name: str
            age: int
            email: str

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
            "input_data": {"name": "John", "age": 30, "email": "john@example.com"},
            "input_validation_prompt": "Age must be greater than 25",
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        assert isinstance(result["data"], str)
        assert len(result["data"]) > 0

    @pytest.mark.timeout(180)
    def test_input_validation_age_constraint_failure(self, http_client):
        """Test input validation failure with age constraint."""

        class Person(BaseModel):
            name: str
            age: int
            email: str

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
            "input_data": {"name": "Jane", "age": 16, "email": "jane@example.com"},
            "input_validation_prompt": "Age must be greater than 18",
        }

        response = self._execute_prompt(http_client, request_data)
        # Should fail with 422 validation error
        assert response.status_code == 422

        result = response.json()
        error_message = result.get("message", "").lower()
        error_details = str(result.get("param", {}).get("errors", [])).lower()
        # Should contain validation error information
        assert "validation" in error_message or "age" in error_message or "age" in error_details

    @pytest.mark.timeout(180)
    def test_input_validation_name_constraint_failure(self, http_client):
        """Test input validation failure with name constraint."""

        class Person(BaseModel):
            name: str
            age: int
            city: str

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
            "input_data": {"name": "John", "age": 30, "city": "New York"},
            "input_validation_prompt": "Name must be exactly 'Alice'",
        }

        response = self._execute_prompt(http_client, request_data)
        # Should fail with 422 validation error
        assert response.status_code == 422

        result = response.json()
        error_message = result.get("message", "").lower()
        error_details = str(result.get("param", {}).get("errors", [])).lower()
        # Should contain validation error information about name
        assert "validation" in error_message or "name" in error_message or "alice" in error_message or "alice" in error_details

    def test_input_validation_complex_nested_model(self, http_client):
        """Test input validation with complex nested model."""

        class Address(BaseModel):
            street: str
            city: str
            country: str

        class Person(BaseModel):
            name: str
            age: int
            address: Address

        class InputSchema(BaseModel):
            content: Person

        class OutputSchema(BaseModel):
            content: str

        # Valid input that should pass validation
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Describe this person and their location"},
            ],
            "input_schema": InputSchema.model_json_schema(),
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": {
                "name": "Alice",
                "age": 28,
                "address": {
                    "street": "123 Main St",
                    "city": "Bangalore",
                    "country": "India"
                }
            },
            "input_validation_prompt": "The person must live in Bangalore city",
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        assert isinstance(result["data"], str)

    @pytest.mark.timeout(180)
    def test_input_validation_nested_model_failure(self, http_client):
        """Test input validation failure with nested model constraint."""

        class Address(BaseModel):
            street: str
            city: str
            country: str

        class Person(BaseModel):
            name: str
            age: int
            address: Address

        class InputSchema(BaseModel):
            content: Person

        class OutputSchema(BaseModel):
            content: str

        # Invalid input that should fail validation
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Describe this person and their location"},
            ],
            "input_schema": InputSchema.model_json_schema(),
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": {
                "name": "Bob",
                "age": 35,
                "address": {
                    "street": "456 Oak St",
                    "city": "Mumbai",
                    "country": "India"
                }
            },
            "input_validation_prompt": "The person must live in Bangalore city",
        }

        response = self._execute_prompt(http_client, request_data)
        # Should fail with 422 validation error
        assert response.status_code == 422

        result = response.json()
        error_message = result.get("message", "").lower()
        error_details = str(result.get("param", {}).get("errors", [])).lower()
        # Should contain validation error information
        assert "validation" in error_message or "bangalore" in error_message or "city" in error_message or "bangalore" in error_details or "city" in error_details

    def test_input_validation_with_list_fields(self, http_client):
        """Test input validation with list fields."""

        class Person(BaseModel):
            name: str
            age: int
            hobbies: list[str]

        class Team(BaseModel):
            team_name: str
            members: list[Person]

        class InputSchema(BaseModel):
            content: Team

        class OutputSchema(BaseModel):
            content: str

        # Valid input that should pass validation
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Describe this team"},
            ],
            "input_schema": InputSchema.model_json_schema(),
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": {
                "team_name": "Alpha Team",
                "members": [
                    {"name": "Alice", "age": 25, "hobbies": ["reading", "coding"]},
                    {"name": "Bob", "age": 30, "hobbies": ["gaming", "music"]},
                    {"name": "Charlie", "age": 28, "hobbies": ["sports", "cooking"]}
                ]
            },
            "input_validation_prompt": "Team must have exactly 3 members and all members must be over 20 years old",
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        assert isinstance(result["data"], str)

    @pytest.mark.timeout(180)
    def test_input_validation_list_constraint_failure(self, http_client):
        """Test input validation failure with list constraint."""

        class Person(BaseModel):
            name: str
            age: int

        class Team(BaseModel):
            team_name: str
            members: list[Person]

        class InputSchema(BaseModel):
            content: Team

        class OutputSchema(BaseModel):
            content: str

        # Invalid input - one member is too young
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Describe this team"},
            ],
            "input_schema": InputSchema.model_json_schema(),
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": {
                "team_name": "Beta Team",
                "members": [
                    {"name": "Alice", "age": 25},
                    {"name": "Bob", "age": 17},  # Too young
                    {"name": "Charlie", "age": 28}
                ]
            },
            "input_validation_prompt": "All team members must be over 18 years old",
        }

        response = self._execute_prompt(http_client, request_data)
        # Should fail with 422 validation error
        assert response.status_code == 422

        result = response.json()
        error_message = result.get("message", "").lower()
        error_details = str(result.get("param", {}).get("errors", [])).lower()
        assert "validation" in error_message or "age" in error_message or "18" in error_message or "age" in error_details or "18" in error_details

    def test_input_validation_multiple_constraints(self, http_client):
        """Test input validation with multiple constraints."""

        class Person(BaseModel):
            name: str
            age: int
            city: str
            email: str

        class InputSchema(BaseModel):
            content: Person

        class OutputSchema(BaseModel):
            content: str

        # Valid input that should pass all constraints
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Describe this person"},
            ],
            "input_schema": InputSchema.model_json_schema(),
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": {
                "name": "Alexander",
                "age": 30,
                "city": "Mumbai",
                "email": "alex@gmail.com"
            },
            "input_validation_prompt": "Name must start with 'A', age must be between 25 and 35, city must be 'Mumbai', and email must contain '@gmail.com'",
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        assert isinstance(result["data"], str)

    def test_input_validation_unstructured_input_ignored(self, http_client):
        """Test that input validation is ignored for unstructured input."""

        class OutputSchema(BaseModel):
            content: str

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Respond to the user's input"},
            ],
            # No input_schema - unstructured input
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Hello, my name is John and I am 16 years old",
            "input_validation_prompt": "Age must be greater than 18",  # Should be ignored
        }

        response = self._execute_prompt(http_client, request_data)
        # Should succeed even though age is < 18 (validation ignored for unstructured)
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        assert isinstance(result["data"], str)

    def test_input_validation_numeric_ranges(self, http_client):
        """Test input validation with numeric range constraints."""

        class Product(BaseModel):
            name: str
            price: float
            rating: float
            quantity: int

        class InputSchema(BaseModel):
            content: Product

        class OutputSchema(BaseModel):
            content: str

        # Valid input within ranges
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Describe this product"},
            ],
            "input_schema": InputSchema.model_json_schema(),
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": {
                "name": "Laptop",
                "price": 55.0,
                "rating": 4.5,
                "quantity": 10
            },
            "input_validation_prompt": "Price must be between 10.0 and 100.0, rating must be between 4.0 and 5.0, quantity must be greater than 0",
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        assert isinstance(result["data"], str)

    def test_input_validation_edge_case_values(self, http_client):
        """Test input validation with edge case values."""

        class Measurement(BaseModel):
            name: str
            value: float
            unit: str
            is_positive: bool

        class InputSchema(BaseModel):
            content: Measurement

        class OutputSchema(BaseModel):
            content: str

        # Valid input with edge case values
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Describe this measurement"},
            ],
            "input_schema": InputSchema.model_json_schema(),
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": {
                "name": "Zero Test",
                "value": 0.0,
                "unit": "meters",
                "is_positive": False
            },
            "input_validation_prompt": "Value must be exactly 0.0, unit must be 'meters', is_positive must be false",
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        assert isinstance(result["data"], str)


# docker exec budserve-development-budprompt pytest tests/test_input_validation_integration.py -v
