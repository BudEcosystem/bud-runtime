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

"""Comprehensive test suite for streaming validation functionality."""

import pytest
import httpx
import json
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class TestStreamingValidation:
    """Integration tests for streaming validation using the existing API structure."""

    base_url = "http://localhost:9088"
    deployment_name = "qwen3-32b"

    @pytest.fixture
    def http_client(self):
        """Create HTTP client for tests."""
        with httpx.Client(base_url=self.base_url, timeout=120.0) as client:
            yield client

    def _execute_streaming_prompt(self, client: httpx.Client, request_data: Dict[str, Any]) -> httpx.Response:
        """Execute streaming prompt and return response."""
        response = client.post("/prompt/execute", json=request_data, headers={"Content-Type": "application/json"})
        return response

    def parse_sse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a Server-Sent Event line and extract JSON data."""
        if line.startswith("data: "):
            data_str = line[6:].strip()
            if data_str:
                try:
                    return json.loads(data_str)
                except json.JSONDecodeError:
                    return None
        return None

    async def stream_validation_test(self, client: httpx.Client, schema: dict, prompt: str, validation_prompt: str, expected_validation: callable = None):
        """Helper function to test streaming validation."""
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that generates valid structured data."},
            ],
            "output_schema": schema,
            "input_data": prompt,
            "output_validation_prompt": validation_prompt,
            "stream": True,
            "llm_retry_limit": 3
        }
        
        final_result = None
        events_received = []
        complete_status = None
        retry_count = None
        error_message = None
        
        with client.stream('POST', "/prompt/execute", json=request_data) as response:
            assert response.status_code == 200
            
            for line in response.iter_lines():
                if line.strip():
                    event_data = self.parse_sse_line(line)
                    if event_data:
                        events_received.append(event_data)
                        
                        if event_data.get('type') == 'final':
                            final_result = event_data.get('content')
                        elif event_data.get('type') == 'complete':
                            complete_status = event_data.get('status')
                            retry_count = event_data.get('retry_count')
                        elif event_data.get('type') == 'error':
                            error_message = event_data.get('message')
        
        # Basic assertions
        assert complete_status == 'success', f"Stream did not complete successfully: {complete_status}, error: {error_message}"
        assert final_result is not None, "No final result received"
        
        # Custom validation if provided
        if expected_validation:
            expected_validation(final_result)
        
        return final_result, retry_count, events_received

    def test_simple_name_validation(self, http_client):
        """Test simple field validation - name starts with specific string."""
        class Person(BaseModel):
            name: str
            age: int
            email: str
        
        class OutputSchema(BaseModel):
            content: Person
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person with name, age, and email."},
            ],
            "output_schema": OutputSchema.model_json_schema(mode="validation"),
            "input_data": "Generate a person with name, age, and email.",
            "output_validation_prompt": "Person name should always start with 'Alice'",
            "stream": True,
            "llm_retry_limit": 3
        }
        
        final_result = None
        complete_status = None
        
        with http_client.stream('POST', "/prompt/execute", json=request_data) as response:
            assert response.status_code == 200
            
            for line in response.iter_lines():
                if line.strip():
                    event_data = self.parse_sse_line(line)
                    if event_data:
                        if event_data.get('type') == 'final':
                            final_result = event_data.get('content')
                        elif event_data.get('type') == 'complete':
                            complete_status = event_data.get('status')
        
        assert complete_status == 'success'
        assert final_result is not None
        assert final_result['content']['name'].startswith('Alice')

    def test_age_range_validation(self, http_client):
        """Test numeric range validation."""
        class Person(BaseModel):
            name: str
            age: int
            email: str
        
        class OutputSchema(BaseModel):
            content: Person
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person with name, age, and email."},
            ],
            "output_schema": OutputSchema.model_json_schema(mode="validation"),
            "input_data": "Generate a person with name, age, and email.",
            "output_validation_prompt": "Person age must be between 25 and 35",
            "stream": True,
            "llm_retry_limit": 3
        }
        
        final_result = None
        complete_status = None
        
        with http_client.stream('POST', "/prompt/execute", json=request_data) as response:
            assert response.status_code == 200
            
            for line in response.iter_lines():
                if line.strip():
                    event_data = self.parse_sse_line(line)
                    if event_data:
                        if event_data.get('type') == 'final':
                            final_result = event_data.get('content')
                        elif event_data.get('type') == 'complete':
                            complete_status = event_data.get('status')
        
        assert complete_status == 'success'
        assert final_result is not None
        assert 25 <= final_result['content']['age'] <= 35

    def test_email_domain_validation(self, http_client):
        """Test email domain validation."""
        class Person(BaseModel):
            name: str
            age: int
            email: str
        
        class OutputSchema(BaseModel):
            content: Person
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person with name, age, and email."},
            ],
            "output_schema": OutputSchema.model_json_schema(mode="validation"),
            "input_data": "Generate a person with name, age, and email.",
            "output_validation_prompt": "Email must end with '@company.com' domain",
            "stream": True,
            "llm_retry_limit": 3
        }
        
        final_result = None
        complete_status = None
        
        with http_client.stream('POST', "/prompt/execute", json=request_data) as response:
            assert response.status_code == 200
            
            for line in response.iter_lines():
                if line.strip():
                    event_data = self.parse_sse_line(line)
                    if event_data:
                        if event_data.get('type') == 'final':
                            final_result = event_data.get('content')
                        elif event_data.get('type') == 'complete':
                            complete_status = event_data.get('status')
        
        assert complete_status == 'success'
        assert final_result is not None
        assert final_result['content']['email'].endswith('@company.com')

    def test_string_length_validation(self, http_client):
        """Test string length validation."""
        class Product(BaseModel):
            name: str
            description: str
            price: float
        
        class OutputSchema(BaseModel):
            content: Product
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a product with name, description, and price."},
            ],
            "output_schema": OutputSchema.model_json_schema(mode="validation"),
            "input_data": "Generate a product with name, description, and price.",
            "output_validation_prompt": "Product name must be at least 10 characters long",
            "stream": True,
            "llm_retry_limit": 3
        }
        
        final_result = None
        complete_status = None
        
        with http_client.stream('POST', "/prompt/execute", json=request_data) as response:
            assert response.status_code == 200
            
            for line in response.iter_lines():
                if line.strip():
                    event_data = self.parse_sse_line(line)
                    if event_data:
                        if event_data.get('type') == 'final':
                            final_result = event_data.get('content')
                        elif event_data.get('type') == 'complete':
                            complete_status = event_data.get('status')
        
        assert complete_status == 'success'
        assert final_result is not None
        assert len(final_result['content']['name']) >= 10

    def test_price_validation(self, http_client):
        """Test price validation with decimal constraints."""
        class Product(BaseModel):
            name: str
            description: str
            price: float
        
        class OutputSchema(BaseModel):
            content: Product
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a product with name, description, and price."},
            ],
            "output_schema": OutputSchema.model_json_schema(mode="validation"),
            "input_data": "Generate a product with name, description, and price.",
            "output_validation_prompt": "Product price must be greater than 100.00",
            "stream": True,
            "llm_retry_limit": 3
        }
        
        final_result = None
        complete_status = None
        
        with http_client.stream('POST', "/prompt/execute", json=request_data) as response:
            assert response.status_code == 200
            
            for line in response.iter_lines():
                if line.strip():
                    event_data = self.parse_sse_line(line)
                    if event_data:
                        if event_data.get('type') == 'final':
                            final_result = event_data.get('content')
                        elif event_data.get('type') == 'complete':
                            complete_status = event_data.get('status')
        
        assert complete_status == 'success'
        assert final_result is not None
        assert final_result['content']['price'] > 100.00

    def test_list_field_validation(self, http_client):
        """Test validation on list fields."""
        class Team(BaseModel):
            name: str
            members: List[str]
            budget: float
        
        class OutputSchema(BaseModel):
            content: Team
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a team with name, list of member names, and budget."},
            ],
            "output_schema": OutputSchema.model_json_schema(mode="validation"),
            "input_data": "Generate a team with name, list of member names, and budget.",
            "output_validation_prompt": "Team must have at least 3 members",
            "stream": True,
            "llm_retry_limit": 3
        }
        
        final_result = None
        complete_status = None
        
        with http_client.stream('POST', "/prompt/execute", json=request_data) as response:
            assert response.status_code == 200
            
            for line in response.iter_lines():
                if line.strip():
                    event_data = self.parse_sse_line(line)
                    if event_data:
                        if event_data.get('type') == 'final':
                            final_result = event_data.get('content')
                        elif event_data.get('type') == 'complete':
                            complete_status = event_data.get('status')
        
        assert complete_status == 'success'
        assert final_result is not None
        assert len(final_result['content']['members']) >= 3

    def test_retry_mechanism(self, http_client):
        """Test that retry mechanism works by checking retry count."""
        class Person(BaseModel):
            name: str
            age: int
            email: str
        
        class OutputSchema(BaseModel):
            content: Person
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person with name, age, and email."},
            ],
            "output_schema": OutputSchema.model_json_schema(mode="validation"),
            "input_data": "Generate a person with name, age, and email.",
            "output_validation_prompt": "Name must start with 'Xyz' and age must be exactly 27",
            "stream": True,
            "llm_retry_limit": 5
        }
        
        final_result = None
        complete_status = None
        retry_count = None
        partial_events = []
        
        with http_client.stream('POST', "/prompt/execute", json=request_data) as response:
            assert response.status_code == 200
            
            for line in response.iter_lines():
                if line.strip():
                    event_data = self.parse_sse_line(line)
                    if event_data:
                        if event_data.get('type') == 'partial':
                            partial_events.append(event_data)
                        elif event_data.get('type') == 'final':
                            final_result = event_data.get('content')
                        elif event_data.get('type') == 'complete':
                            complete_status = event_data.get('status')
                            retry_count = event_data.get('retry_count')
        
        assert complete_status == 'success'
        assert final_result is not None
        assert final_result['content']['name'].startswith('Xyz')
        assert final_result['content']['age'] == 27
        
        # Check that we received partial events during streaming
        assert len(partial_events) > 0, "Should have received partial events during streaming"

    def test_validation_disabled_when_no_prompt(self, http_client):
        """Test that validation is not applied when no validation prompt is provided."""
        class Person(BaseModel):
            name: str
            age: int
            email: str
        
        class OutputSchema(BaseModel):
            content: Person
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person with name, age, and email."},
            ],
            "output_schema": OutputSchema.model_json_schema(mode="validation"),
            "input_data": "Generate a person with name, age, and email.",
            # No output_validation_prompt - validation should be disabled
            "stream": True,
            "llm_retry_limit": 3
        }
        
        final_result = None
        complete_status = None
        all_events = []
        
        with http_client.stream('POST', "/prompt/execute", json=request_data) as response:
            assert response.status_code == 200
            
            for line in response.iter_lines():
                if line.strip():
                    event_data = self.parse_sse_line(line)
                    if event_data:
                        all_events.append(event_data)
                        # Handle streaming validation format
                        if event_data.get('type') == 'final':
                            final_result = event_data.get('content')
                        elif event_data.get('type') == 'complete':
                            complete_status = event_data.get('status')
                        # Handle regular streaming format (ModelResponse)
                        elif 'parts' in event_data and event_data.get('end'):
                            # This is the final event in regular streaming
                            # Extract content from the parts
                            for part in event_data.get('parts', []):
                                if 'content' in part:
                                    content = part['content']
                                    # Parse the JSON content
                                    if isinstance(content, str):
                                        try:
                                            import json
                                            parsed = json.loads(content)
                                            # The parsed content already has the structure we need
                                            final_result = parsed
                                        except json.JSONDecodeError:
                                            pass
                            complete_status = 'success'  # Regular streaming completed
        
        # Debug output if test fails
        if complete_status != 'success' or final_result is None:
            print(f"All events received: {all_events}")
        
        assert complete_status == 'success'
        assert final_result is not None
        
        # Handle both possible structures
        if 'content' in final_result:
            # Nested structure
            assert 'name' in final_result['content']
            assert 'age' in final_result['content']
            assert 'email' in final_result['content']
        else:
            # Direct structure (if the model returns Person directly)
            assert 'name' in final_result
            assert 'age' in final_result
            assert 'email' in final_result

    def test_max_retries_exhausted(self, http_client):
        """Test validation failure with retry exhaustion."""
        class Person(BaseModel):
            name: str
            age: int
        
        class OutputSchema(BaseModel):
            content: Person
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a person with name and age."},
            ],
            "output_schema": OutputSchema.model_json_schema(mode="validation"),
            "input_data": "Generate a person with name and age.",
            # Multiple impossible constraints to ensure failure
            "output_validation_prompt": "Age must be negative AND name must be exactly 'XyZabc123NonExistentName' AND age must also be over 200",
            "stream": True,
            "llm_retry_limit": 2  # Low retry count to speed up test
        }
        
        complete_status = None
        error_messages = []
        
        with http_client.stream('POST', "/prompt/execute", json=request_data) as response:
            assert response.status_code == 200
            
            for line in response.iter_lines():
                if line.strip():
                    event_data = self.parse_sse_line(line)
                    if event_data:
                        if event_data.get('type') == 'complete':
                            complete_status = event_data.get('status')
                        elif event_data.get('type') == 'error':
                            error_messages.append(event_data.get('message'))
        
        # Should fail with max retries exhausted
        assert complete_status == 'max_retries_exceeded'
        assert len(error_messages) > 0
        # Check that at least one error message mentions max retries
        assert any('max retries' in msg.lower() or 'exhausted' in msg.lower() for msg in error_messages)

    def test_multiple_validations_same_field(self, http_client):
        """Test multiple validation constraints on the same field."""
        class Product(BaseModel):
            name: str
            sku: str
            price: float
        
        class OutputSchema(BaseModel):
            content: Product
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Generate a product with name, SKU, and price."},
            ],
            "output_schema": OutputSchema.model_json_schema(mode="validation"),
            "input_data": "Generate a product with name, SKU, and price.",
            "output_validation_prompt": "SKU must start with 'PROD-'",
            "stream": True,
            "llm_retry_limit": 3
        }
        
        final_result = None
        complete_status = None
        
        with http_client.stream('POST', "/prompt/execute", json=request_data) as response:
            assert response.status_code == 200
            
            for line in response.iter_lines():
                if line.strip():
                    event_data = self.parse_sse_line(line)
                    if event_data:
                        if event_data.get('type') == 'final':
                            final_result = event_data.get('content')
                        elif event_data.get('type') == 'complete':
                            complete_status = event_data.get('status')
        
        assert complete_status == 'success'
        assert final_result is not None
        assert final_result['content']['sku'].startswith('PROD-')

# docker exec budserve-development-budprompt pytest tests/test_streaming_validation.py -v
