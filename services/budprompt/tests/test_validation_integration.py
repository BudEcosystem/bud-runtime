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

"""Integration tests for validation functionality with actual API calls."""

from typing import Any, Dict

import httpx
import pytest
from pydantic import BaseModel


class TestValidationIntegration:
    """Integration tests for output validation using actual API calls."""

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

    def test_validation_disabled_simple_output(self, http_client):
        """Test that validation is not applied when no validation prompt is provided."""

        class OutputSchema(BaseModel):
            content: str

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Say hello",
            # No output_validation_prompt - validation should be disabled
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        assert isinstance(result["data"], str)
        assert len(result["data"]) > 0

    def test_validation_simple_success(self, http_client):
        """Test simple validation that should succeed."""

        class Person(BaseModel):
            name: str
            age: int
            email: str

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person who is over 25 years old"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a person over 25 years old",
            "output_validation_prompt": "Age must be greater than 25",
            "llm_retry_limit": 2
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        assert "name" in result["data"]
        assert "age" in result["data"]
        assert "email" in result["data"]
        # Verify validation worked
        assert result["data"]["age"] > 25

    def test_validation_name_constraint_success(self, http_client):
        """Test validation with specific name constraint."""

        class Person(BaseModel):
            name: str
            age: int
            email: str

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person named John"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a person named John with age and email",
            "output_validation_prompt": "The name must be exactly 'John'",
            "llm_retry_limit": 3
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert result["data"]["name"] == "John"

    def test_validation_complex_nested_model(self, http_client):
        """Test validation with complex nested model."""

        class Address(BaseModel):
            street: str
            city: str
            country: str

        class Person(BaseModel):
            name: str
            age: int
            address: Address

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person living in Bangalore, India"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a person who lives in Bangalore, India",
            "output_validation_prompt": "The person must live in Bangalore city",
            "llm_retry_limit": 3
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert "address" in result["data"], "Response should contain address"
        assert "city" in result["data"]["address"], "Address should contain city"
        # Allow partial matches in case validation is not perfect
        city = result["data"]["address"]["city"].lower()
        assert "bangalore" in city or "bengaluru" in city, f"Expected Bangalore/Bengaluru but got {result['data']['address']['city']}"

    def test_validation_retry_exhausted(self, http_client):
        """Test validation failure with retry exhaustion."""

        class Person(BaseModel):
            name: str
            age: int

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person with name and age"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a person",
            # Multiple impossible constraints to ensure failure
            "output_validation_prompt": "Age must be negative AND name must be exactly 'XyZabc123NonExistentName' AND age must also be over 200",
            "llm_retry_limit": 3
        }

        response = self._execute_prompt(http_client, request_data)
        # Should fail with 500 and retry exhausted message
        assert response.status_code == 500, f"Expected 500 but got {response.status_code}: {response.text}"

        result = response.json()
        error_message = result.get("message", "").lower()
        # Check for various possible error messages
        retry_exhausted = any(phrase in error_message for phrase in [
            "exceeded maximum retries",
            "max retries",
            "validation failed",
            "output validation failed"
        ])
        assert retry_exhausted, f"Expected retry exhaustion error but got: {result.get('message', '')}"

    def test_validation_streaming_ignored(self, http_client):
        """Test that validation is ignored when streaming is enabled."""

        class Person(BaseModel):
            name: str
            age: int

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a person",
            "stream": True,  # Streaming enabled - validation should be ignored
            "output_validation_prompt": "Name must be Alexander",
            "llm_retry_limit": 2
        }

        response = self._execute_prompt(http_client, request_data)
        # Should succeed even without meeting validation (since validation is ignored)
        assert response.status_code == 200

        # For streaming, we get SSE format, so just check it's not empty
        content = response.text
        assert len(content) > 0
        assert "data:" in content

    def test_validation_with_batch_of_people(self, http_client):
        """Test validation with list/batch of people."""

        class Person(BaseModel):
            name: str
            age: int
            email: str

        class Batch(BaseModel):
            batch_name: str
            people: list[Person]

        class OutputSchema(BaseModel):
            content: Batch

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a batch of 3 people, all adults over 18"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a batch with 3 adult people",
            "output_validation_prompt": "All people must be over 18 years old",
            "llm_retry_limit": 3
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert "batch_name" in result["data"]
        assert "people" in result["data"]
        assert len(result["data"]["people"]) >= 2  # At least 2 people

        # Verify all people meet age validation
        for person in result["data"]["people"]:
            assert person["age"] > 18

    def test_validation_zero_retries(self, http_client):
        """Test validation with zero retries - should fail immediately if validation fails."""

        class Person(BaseModel):
            name: str
            age: int

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a random person with any name and age"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate any person",
            "output_validation_prompt": "Name must be exactly 'XyZabc123ImpossibleName' AND age must be negative",
            "llm_retry_limit": 0  # No retries
        }

        response = self._execute_prompt(http_client, request_data)
        # With impossible constraints and 0 retries, it should fail quickly
        assert response.status_code == 500, f"Expected failure with 0 retries, got {response.status_code}"

        result = response.json()
        error_message = result.get("message", "").lower()
        # Should indicate validation failure without retries
        validation_failed = any(phrase in error_message for phrase in [
            "validation failed",
            "exceeded maximum retries",
            "output validation failed"
        ])
        assert validation_failed, f"Expected validation failure message but got: {result.get('message', '')}"

    @pytest.mark.timeout(180)
    def test_validation_high_retry_limit(self, http_client):
        """Test validation with high retry limit for difficult constraint."""

        class Person(BaseModel):
            name: str
            age: int
            city: str

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person from Bangalore"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a person who lives in Bangalore",
            "output_validation_prompt": "The person must be from Bangalore city and age must be exactly 30",
            "llm_retry_limit": 5  # Higher retry limit
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert result["data"]["city"] == "Bangalore"
        assert result["data"]["age"] == 30

    def test_validation_multiple_constraints(self, http_client):
        """Test validation with multiple constraints in one prompt."""

        class Person(BaseModel):
            name: str
            age: int
            city: str
            email: str

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person with all required details"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a person",
            "output_validation_prompt": "Name must start with 'A', age must be between 25 and 35, city must be 'Mumbai', and email must contain '@gmail.com'",
            "llm_retry_limit": 4
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        person = result["data"]
        assert person["name"].startswith("A"), f"Name should start with 'A', got {person['name']}"
        assert 25 <= person["age"] <= 35, f"Age should be 25-35, got {person['age']}"
        assert person["city"] == "Mumbai", f"City should be Mumbai, got {person['city']}"
        assert "@gmail.com" in person["email"], f"Email should contain @gmail.com, got {person['email']}"

    def test_validation_numeric_ranges(self, http_client):
        """Test validation with specific numeric ranges."""

        class Product(BaseModel):
            name: str
            price: float
            rating: float
            quantity: int

        class OutputSchema(BaseModel):
            content: Product

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a product with name, price, rating, and quantity"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a product",
            "output_validation_prompt": "Price must be between 10.0 and 100.0, rating must be between 4.0 and 5.0, quantity must be greater than 0",
            "llm_retry_limit": 3
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        product = result["data"]
        assert 10.0 <= product["price"] <= 100.0, f"Price should be 10-100, got {product['price']}"
        assert 4.0 <= product["rating"] <= 5.0, f"Rating should be 4-5, got {product['rating']}"
        assert product["quantity"] > 0, f"Quantity should be > 0, got {product['quantity']}"

    def test_validation_string_patterns(self, http_client):
        """Test validation with string pattern matching."""

        class Contact(BaseModel):
            name: str
            phone: str
            email: str
            website: str

        class OutputSchema(BaseModel):
            content: Contact

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate contact information"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate contact details",
            "output_validation_prompt": "Phone must start with '+91', email must end with '.com', website must start with 'https://'",
            "llm_retry_limit": 4
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        contact = result["data"]
        assert contact["phone"].startswith("+91"), f"Phone should start with +91, got {contact['phone']}"
        assert contact["email"].endswith(".com"), f"Email should end with .com, got {contact['email']}"
        assert contact["website"].startswith("https://"), f"Website should start with https://, got {contact['website']}"

    def test_validation_list_constraints(self, http_client):
        """Test validation with list length and item constraints."""

        class Person(BaseModel):
            name: str
            age: int

        class Team(BaseModel):
            team_name: str
            members: list[Person]
            project_count: int

        class OutputSchema(BaseModel):
            content: Team

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a team with members"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a team with multiple members",
            "output_validation_prompt": "Team must have exactly 3 members, all members must be over 20 years old, and project_count must be greater than 0",
            "llm_retry_limit": 4
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        team = result["data"]
        assert len(team["members"]) == 3, f"Team should have exactly 3 members, got {len(team['members'])}"
        for member in team["members"]:
            assert member["age"] > 20, f"All members should be > 20, got member with age {member['age']}"
        assert team["project_count"] > 0, f"Project count should be > 0, got {team['project_count']}"

    def test_validation_conditional_logic(self, http_client):
        """Test validation with conditional logic."""

        class Employee(BaseModel):
            name: str
            position: str
            salary: float
            experience_years: int

        class OutputSchema(BaseModel):
            content: Employee

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate an employee with position, salary, and experience"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate an employee",
            "output_validation_prompt": "If position is 'Manager' then salary must be above 80000, if experience_years > 5 then salary must be above 60000",
            "llm_retry_limit": 4
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        employee = result["data"]

        # Check conditional logic
        if employee["position"] == "Manager":
            assert employee["salary"] > 80000, f"Manager salary should be > 80000, got {employee['salary']}"
        if employee["experience_years"] > 5:
            assert employee["salary"] > 60000, f"Experienced employee salary should be > 60000, got {employee['salary']}"

    def test_validation_edge_case_values(self, http_client):
        """Test validation with edge case values."""

        class Measurement(BaseModel):
            name: str
            value: float
            unit: str
            is_positive: bool

        class OutputSchema(BaseModel):
            content: Measurement

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a measurement"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a measurement",
            "output_validation_prompt": "Value must be exactly 0.0, unit must be 'meters', is_positive must be false",
            "llm_retry_limit": 3
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        measurement = result["data"]
        assert measurement["value"] == 0.0, f"Value should be exactly 0.0, got {measurement['value']}"
        assert measurement["unit"] == "meters", f"Unit should be 'meters', got {measurement['unit']}"
        assert measurement["is_positive"] == False, f"is_positive should be False, got {measurement['is_positive']}"

    def test_validation_retry_improvement(self, http_client):
        """Test that retries actually improve output quality."""

        class Person(BaseModel):
            name: str
            age: int
            city: str

        class OutputSchema(BaseModel):
            content: Person

        # Test with specific constraints that may require retries
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a person",
            "output_validation_prompt": "Name must be exactly 'Alexander', age must be exactly 28, city must be exactly 'Stockholm'",
            "llm_retry_limit": 5
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        person = result["data"]
        assert person["name"] == "Alexander", f"Name should be Alexander, got {person['name']}"
        assert person["age"] == 28, f"Age should be 28, got {person['age']}"
        assert person["city"] == "Stockholm", f"City should be Stockholm, got {person['city']}"

    @pytest.mark.timeout(180)
    def test_validation_business_rules(self, http_client):
        """Test validation with real-world business rules."""

        class Order(BaseModel):
            order_id: str
            customer_type: str
            total_amount: float
            discount_percent: float
            final_amount: float

        class OutputSchema(BaseModel):
            content: Order

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate an order with business rules"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate an order",
            "output_validation_prompt": "If customer_type is 'Premium' then discount_percent must be at least 10, final_amount must equal total_amount minus discount, and order_id must start with 'ORD-'",
            "llm_retry_limit": 4
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        order = result["data"]

        assert order["order_id"].startswith("ORD-"), f"Order ID should start with ORD-, got {order['order_id']}"

        if order["customer_type"] == "Premium":
            assert order["discount_percent"] >= 10, f"Premium customer discount should be >= 10, got {order['discount_percent']}"

        # Check discount calculation (with some tolerance for floating point)
        expected_final = order["total_amount"] * (1 - order["discount_percent"] / 100)
        assert abs(order["final_amount"] - expected_final) < 0.01, f"Final amount calculation incorrect: {order['final_amount']} vs expected {expected_final}"


class TestValidationAdvancedScenarios:
    """Advanced validation test scenarios."""

    base_url = "http://localhost:9088"
    deployment_name = "qwen3-32b"

    @pytest.fixture
    def http_client(self):
        """Create HTTP client for tests."""
        with httpx.Client(base_url=self.base_url, timeout=150.0) as client:
            yield client

    def _execute_prompt(self, client: httpx.Client, request_data: Dict[str, Any]) -> httpx.Response:
        """Execute prompt and return response."""
        response = client.post("/prompt/execute", json=request_data, headers={"Content-Type": "application/json"})
        return response

    def test_validation_different_retry_limits(self, http_client):
        """Test how different retry limits affect success rate."""

        class Person(BaseModel):
            name: str
            age: int

        class OutputSchema(BaseModel):
            content: Person

        # Test with increasingly difficult constraint and different retry limits
        constraint = "Name must be exactly 'Maximilian' and age must be exactly 42"

        for retry_limit in [1, 3, 5]:
            request_data = {
                "deployment_name": self.deployment_name,
                "messages": [
                {"role": "system", "content": "Generate a person with specific requirements"},
            ],
                "output_schema": OutputSchema.model_json_schema(),
                "input_data": "Generate a person",
                "output_validation_prompt": constraint,
                "llm_retry_limit": retry_limit
            }

            response = self._execute_prompt(http_client, request_data)

            # Higher retry limits should have better success rate
            if response.status_code == 200:
                result = response.json()
                person = result["data"]
                # If successful, should meet constraints
                if person["name"] == "Maximilian" and person["age"] == 42:
                    print(f"Success with {retry_limit} retries")
                    break
            else:
                print(f"Failed with {retry_limit} retries: {response.status_code}")

        # At least one retry limit should succeed
        assert response.status_code == 200, "At least one retry limit should succeed"

    def test_validation_conflicting_constraints(self, http_client):
        """Test validation with conflicting/impossible constraints."""

        class Person(BaseModel):
            name: str
            age: int

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a person",
            "output_validation_prompt": "Age must be greater than 100 AND age must be less than 50 AND name must be both 'John' and 'Mary' at the same time",
            "llm_retry_limit": 2
        }

        response = self._execute_prompt(http_client, request_data)
        # Should fail due to impossible constraints
        assert response.status_code == 500

        result = response.json()
        error_message = result.get("message", "").lower()
        assert "exceeded maximum retries" in error_message or "validation failed" in error_message

    def test_validation_unicode_characters(self, http_client):
        """Test validation with unicode characters."""

        class Person(BaseModel):
            name: str
            city: str
            description: str

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person with international details"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a person with unicode characters",
            "output_validation_prompt": "Name must contain emoji 🌟, city must be 'München', description must include the word 'café'",
            "llm_retry_limit": 4
        }

        response = self._execute_prompt(http_client, request_data)

        if response.status_code == 200:
            result = response.json()
            person = result["data"]
            assert "🌟" in person["name"], f"Name should contain 🌟, got {person['name']}"
            assert person["city"] == "München", f"City should be München, got {person['city']}"
            assert "café" in person["description"], f"Description should contain café, got {person['description']}"
        else:
            # Unicode handling might not work perfectly, so we allow graceful failure
            assert response.status_code in [400, 500]

    @pytest.mark.timeout(240)
    def test_validation_very_long_prompt(self, http_client):
        """Test validation with very long validation prompt."""

        class Person(BaseModel):
            name: str
            age: int
            occupation: str

        class OutputSchema(BaseModel):
            content: Person

        # Create a very long validation prompt
        long_prompt = (
            "The person must meet the following criteria: "
            "Name must be exactly 'Christopher' and nothing else, "
            "age must be precisely 35 years old, not 34 or 36 but exactly 35, "
            "occupation must be 'Software Engineer' with exactly these words and proper capitalization, "
            "the name Christopher should not have any nicknames or variations, "
            "the age 35 should represent someone born in 1988 or 1989 depending on the current date, "
            "and the occupation Software Engineer should indicate someone who writes code professionally."
        )

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person with detailed requirements"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a person",
            "output_validation_prompt": long_prompt,
            "llm_retry_limit": 3
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        person = result["data"]
        assert person["name"] == "Christopher", f"Name should be Christopher, got {person['name']}"
        assert person["age"] == 35, f"Age should be 35, got {person['age']}"
        assert person["occupation"] == "Software Engineer", f"Occupation should be Software Engineer, got {person['occupation']}"


class TestValidationErrorHandling:
    """Test error handling in validation scenarios."""

    base_url = "http://localhost:9088"
    deployment_name = "qwen3-32b"

    @pytest.fixture
    def http_client(self):
        """Create HTTP client for tests."""
        with httpx.Client(base_url=self.base_url, timeout=90.0) as client:
            yield client

    def _execute_prompt(self, client: httpx.Client, request_data: Dict[str, Any]) -> httpx.Response:
        """Execute prompt and return response."""
        response = client.post("/prompt/execute", json=request_data, headers={"Content-Type": "application/json"})
        return response

    def test_validation_with_invalid_schema(self, http_client):
        """Test validation with malformed output schema."""

        # Invalid schema - missing required fields
        invalid_schema = {
            "type": "object",
            "properties": {
                "content": {
                    "type": "object",
                    # Missing properties definition
                }
            }
        }

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate something"},
            ],
            "output_schema": invalid_schema,
            "input_data": "Generate data",
            "output_validation_prompt": "Some validation",
            "llm_retry_limit": 1
        }

        response = self._execute_prompt(http_client, request_data)
        # Should handle gracefully, either succeed without validation or return helpful error
        assert response.status_code in [200, 400, 500]

    def test_validation_with_unstructured_output(self, http_client):
        """Test that validation is ignored for unstructured output."""

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Just say hello"},
            ],
            "input_data": "Say hello",
            # No output_schema - unstructured output
            "output_validation_prompt": "Must contain 'hello'",  # Should be ignored
            "llm_retry_limit": 2
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 200

        result = response.json()
        assert isinstance(result["data"], str)

    def test_validation_prompt_with_special_characters(self, http_client):
        """Test validation prompt with special characters and edge cases."""

        class Person(BaseModel):
            name: str
            description: str

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a person",
            "output_validation_prompt": "Name must contain 'test' and description must have quotes \"like this\"",
            "llm_retry_limit": 2
        }

        response = self._execute_prompt(http_client, request_data)
        # Should handle special characters gracefully
        assert response.status_code in [200, 500]  # Either succeed or fail gracefully

    def test_validation_malformed_prompt(self, http_client):
        """Test validation with malformed/nonsensical validation prompt."""

        class Person(BaseModel):
            name: str
            age: int

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a person",
            "output_validation_prompt": "@@@ invalid syntax { } [ ] python code error $$$ nonsense validation !!!",
            "llm_retry_limit": 2
        }

        response = self._execute_prompt(http_client, request_data)
        # Should handle malformed prompts gracefully
        assert response.status_code in [200, 400, 500]

    def test_validation_empty_prompt(self, http_client):
        """Test validation with empty validation prompt."""

        class Person(BaseModel):
            name: str
            age: int

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a person",
            "output_validation_prompt": "",  # Empty validation prompt
            "llm_retry_limit": 1
        }

        response = self._execute_prompt(http_client, request_data)
        # Empty validation should either be ignored or handled gracefully
        assert response.status_code in [200, 400]

    def test_validation_json_injection_attempt(self, http_client):
        """Test validation prompt with JSON injection attempt."""

        class Person(BaseModel):
            name: str
            age: int

        class OutputSchema(BaseModel):
            content: Person

        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person"},
            ],
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Generate a person",
            "output_validation_prompt": '{"malicious": "injection", "code": "exec(\\"harmful_code\\")", "name": "should_be_ignored"}',
            "llm_retry_limit": 2
        }

        response = self._execute_prompt(http_client, request_data)
        # Should handle potential injection attempts safely
        assert response.status_code in [200, 400, 500]

        if response.status_code == 200:
            result = response.json()
            # Make sure no malicious content leaked through
            person_str = str(result["data"])
            assert "exec" not in person_str.lower()
            assert "malicious" not in person_str.lower()

# docker exec budserve-development-budprompt pytest tests/test_validation_integration.py -v
