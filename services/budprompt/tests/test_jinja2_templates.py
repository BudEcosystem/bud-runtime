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

"""Comprehensive test cases for Jinja2 template support in prompts and messages."""

import httpx
import pytest
from typing import Dict, Any, List
from pydantic import BaseModel


class TestJinja2Templates:
    """Test suite for Jinja2 template rendering in prompts and messages."""

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

    # ========== Basic Template Tests ==========

    def test_no_templates_backward_compatibility(self, http_client):
        """Test that non-templated prompts still work (backward compatibility)."""
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is 2 + 2?"}
            ],
            "input_data": None,
        }

        response = self._execute_prompt(http_client, request_data)
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        assert "4" in str(result["data"])

    def test_simple_system_prompt_no_template(self, http_client):
        """Test simple system prompt without templates."""
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant specialized in programming."},
                {"role": "user", "content": "Say hello"}
            ],
            "input_data": None,
        }

        response = self._execute_prompt(http_client, request_data)
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        # Should respond with something
        assert len(result["data"]) > 0

    # ========== Unstructured String Input Tests ==========

    def test_unstructured_input_with_system_template(self, http_client):
        """Test system prompt template with unstructured string input."""
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Summarize the following text: {{ input }}"}
            ],
            "input_data": "The quick brown fox jumps over the lazy dog. This is a pangram containing all letters of the alphabet."
        }

        response = self._execute_prompt(http_client, request_data)
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        response_text = result["data"].lower()
        assert "pangram" in response_text or "letters" in response_text or "alphabet" in response_text

    def test_unstructured_with_message_template(self, http_client):
        """Test message template with unstructured input."""
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Analyze this: {{ input }}"}
            ],
            "input_data": "Python is a high-level programming language."
        }

        response = self._execute_prompt(http_client, request_data)
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        assert "python" in result["data"].lower()

    # ========== Structured Input Tests ==========

    def test_structured_input_with_system_template(self, http_client):
        """Test system prompt template with structured input data."""
        
        class TemplateData(BaseModel):
            personality: str
            domain: str
            
        class InputSchema(BaseModel):
            content: TemplateData
        
        request_data = {
            "deployment_name": "qwen3-32b",  # Use larger model for better system prompt following
            "messages": [
                {"role": "system", "content": "You are a {{ content.personality }} assistant specialized in {{ content.domain }}."},
                {"role": "user", "content": "What can you help me with?"}
            ],
            "input_schema": InputSchema.model_json_schema(),
            "input_data": {
                "content": {
                    "personality": "helpful and friendly",
                    "domain": "Python programming"
                }
            },
        }

        response = self._execute_prompt(http_client, request_data)
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        response_text = result["data"].lower()
        assert "python" in response_text or "programming" in response_text

    def test_structured_input_with_message_templates(self, http_client):
        """Test message content templates with structured input."""
        
        class UserInfo(BaseModel):
            name: str
            topic: str
            
        class InputSchema(BaseModel):
            content: UserInfo
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": "My name is {{ content.name }} and I need help with {{ content.topic }}."
                }
            ],
            "input_schema": InputSchema.model_json_schema(),
            "input_data": {
                "content": {
                    "name": "Alice",
                    "topic": "machine learning"
                }
            },
        }

        response = self._execute_prompt(http_client, request_data)
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        response_text = result["data"].lower()
        assert "alice" in response_text or "machine learning" in response_text

    def test_template_with_list_data(self, http_client):
        """Test templates with list data in structured input."""
        
        class ItemList(BaseModel):
            fruits: List[str]
            
        class InputSchema(BaseModel):
            content: ItemList
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": "Please analyze these items: {% for item in content.fruits %}{{ item }}{% if not loop.last %}, {% endif %}{% endfor %}"
                }
            ],
            "input_schema": InputSchema.model_json_schema(),
            "input_data": {
                "content": {
                    "fruits": ["apple", "banana", "orange"]
                }
            },
        }

        response = self._execute_prompt(http_client, request_data)
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        response_text = result["data"].lower()
        assert any(fruit in response_text for fruit in ["apple", "banana", "orange"])

    def test_template_with_conditionals(self, http_client):
        """Test Jinja2 conditional statements."""
        
        class TaskInfo(BaseModel):
            is_urgent: bool
            task: str
            deadline: str
            
        class InputSchema(BaseModel):
            content: TaskInfo
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": "{% if content.is_urgent %}URGENT: {% endif %}Please help me with {{ content.task }}{% if content.deadline %} by {{ content.deadline }}{% endif %}."
                }
            ],
            "input_schema": InputSchema.model_json_schema(),
            "input_data": {
                "content": {
                    "is_urgent": True,
                    "task": "reviewing this document",
                    "deadline": "end of day"
                }
            },
        }

        response = self._execute_prompt(http_client, request_data)
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        response_text = result["data"].lower()
        # Check that the URGENT prefix made it through the template
        assert any(word in response_text for word in ["urgent", "urgency", "immediately", "right away", "priority"])

    def test_template_with_filters(self, http_client):
        """Test Jinja2 filters in templates."""
        
        class TextData(BaseModel):
            case_type: str
            text: str
            
        class InputSchema(BaseModel):
            content: TextData
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": "Convert this to {{ content.case_type }}: {{ content.text|upper }}"
                }
            ],
            "input_schema": InputSchema.model_json_schema(),
            "input_data": {
                "content": {
                    "case_type": "uppercase",
                    "text": "hello world"
                }
            },
        }

        response = self._execute_prompt(http_client, request_data)
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        assert "HELLO WORLD" in result["data"]

    # ========== Conversation and Role Tests ==========

    def test_conversation_with_all_roles(self, http_client):
        """Test full conversation with all roles and templates."""
        
        class MathProblem(BaseModel):
            multiplier: int
            
        class InputSchema(BaseModel):
            content: MathProblem
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "You are a helpful math tutor."},
                {
                    "role": "developer",
                    "content": "Always show your work step by step."
                },
                {
                    "role": "user",
                    "content": "What is 15 + 27?"
                },
                {
                    "role": "assistant",
                    "content": "Let me solve this step by step:\n15 + 27 = 42"
                },
                {
                    "role": "user",
                    "content": "Now what is that result multiplied by {{ content.multiplier }}?"
                }
            ],
            "input_schema": InputSchema.model_json_schema(),
            "input_data": {
                "content": {
                    "multiplier": 2
                }
            },
        }

        response = self._execute_prompt(http_client, request_data)
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        # Should calculate 42 * 2 = 84
        assert "84" in str(result["data"])

    def test_developer_role_as_system_instruction(self, http_client):
        """Test that developer role messages are treated as system-level instructions."""
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "You are a Python expert."},
                {
                    "role": "developer",
                    "content": "Always use type hints in Python code examples."
                },
                {
                    "role": "user",
                    "content": "Show me a function to add two numbers"
                }
            ],
            "input_data": None,
        }

        response = self._execute_prompt(http_client, request_data)
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        # Should include type hints
        assert "->" in result["data"] or ": int" in result["data"]

    def test_multiple_user_messages_with_templates(self, http_client):
        """Test multiple user messages with different template variables."""
        
        class TravelData(BaseModel):
            origin: str
            destination: str
            duration: int
            
        class InputSchema(BaseModel):
            content: TravelData
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "You are a travel assistant."},
                {
                    "role": "user",
                    "content": "I want to travel from {{ content.origin }}."
                },
                {
                    "role": "assistant",
                    "content": "I can help you plan your trip from London. Where would you like to go?"
                },
                {
                    "role": "user",
                    "content": "I'd like to go to {{ content.destination }} for {{ content.duration }} days."
                }
            ],
            "input_schema": InputSchema.model_json_schema(),
            "input_data": {
                "content": {
                    "origin": "London",
                    "destination": "Paris",
                    "duration": 5
                }
            },
        }

        response = self._execute_prompt(http_client, request_data)
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        response_text = result["data"].lower()
        assert "paris" in response_text

    # ========== Edge Cases and Error Handling ==========

    def test_empty_messages_with_structured_input(self, http_client):
        """Test when messages array is empty but structured input_data is provided."""
        
        class BusinessData(BaseModel):
            sales: int
            growth: int
            region: str
            
        class InputSchema(BaseModel):
            content: BusinessData
        
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "Process this data and provide insights."}
            ],
            "input_schema": InputSchema.model_json_schema(),
            "input_data": {
                "content": {
                    "sales": 1000,
                    "growth": 15,
                    "region": "North America"
                }
            },
        }

        response = self._execute_prompt(http_client, request_data)
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        assert response.status_code == 200

        result = response.json()
        assert "data" in result
        response_text = result["data"].lower()
        assert any(term in response_text for term in ["sales", "growth", "north america", "1000", "15"])

    def test_missing_template_variable(self, http_client):
        """Test behavior when template variable is missing (should use empty string)."""
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "You are a {{ personality }} assistant."},
                {"role": "user", "content": "Hello"}
            ],
            "input_data": "test",  # String input, but template expects 'personality'
        }

        response = self._execute_prompt(http_client, request_data)
        if response.status_code != 200:
            print(f"Error response: {response.json()}")
        assert response.status_code == 200  # Should still work, Jinja2 replaces with empty string

        result = response.json()
        assert "data" in result

    def test_invalid_template_syntax(self, http_client):
        """Test error handling for invalid Jinja2 syntax."""
        request_data = {
            "deployment_name": self.deployment_name,
            "messages": [
                {"role": "system", "content": "You are a {{ personality assistant.}"},  # Missing closing }}
                {"role": "user", "content": "Hello"}
            ],
            "input_data": "test",
        }

        response = self._execute_prompt(http_client, request_data)
        assert response.status_code == 400  # Should fail with template syntax error
        if response.status_code == 400:
            error_response = response.json()
            assert "template" in str(error_response).lower() or "syntax" in str(error_response).lower()

# docker exec budserve-development-budprompt pytest tests/test_jinja2_templates.py -v