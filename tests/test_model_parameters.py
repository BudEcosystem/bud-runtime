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

"""Test cases for all model parameters including BudEcosystem-specific ones."""

from typing import Any, Dict, List

import httpx
import pytest
from pydantic import BaseModel


class TestModelParameters:
    """Test suite for all model parameters using actual model inference."""

    base_url = "http://localhost:9088"
    deployment_name = "qwen3-4b"

    @pytest.fixture
    def http_client(self):
        """Create HTTP client for tests."""
        with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
            yield client

    def _execute_prompt(
        self, client: httpx.Client, model_settings: Dict[str, Any], input_data: str = "Hello", **kwargs
    ) -> httpx.Response:
        """Execute prompt with specific model settings.
        
        Args:
            client: HTTP client
            model_settings: Model configuration settings
            input_data: Input prompt text
            **kwargs: Additional request parameters (e.g., stream=True, tools=[...])
        """

        class OutputSchema(BaseModel):
            content: str

        request_data = {
            "deployment_name": self.deployment_name,
            "system_prompt": "You are a helpful assistant. Respond briefly.",
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": input_data,
            "model_settings": model_settings,
        }
        
        # Merge any additional kwargs into request_data
        request_data.update(kwargs)

        response = client.post("/prompt/execute", json=request_data, headers={"Content-Type": "application/json"})
        return response

    # Standard OpenAI Parameters Tests

    def test_temperature(self, http_client):
        """Test temperature parameter (0-2)."""
        # Test low temperature (more deterministic)
        model_settings = {"temperature": 0.1}
        response = self._execute_prompt(http_client, model_settings, "What is 2+2?")
        assert response.status_code == 200
        result = response.json()
        assert "data" in result

        # Test high temperature (more creative)
        model_settings = {"temperature": 1.8}
        response = self._execute_prompt(http_client, model_settings, "Tell me a story in 10 words")
        assert response.status_code == 200

    def test_max_tokens(self, http_client):
        """Test max_tokens parameter."""
        model_settings = {"max_tokens": 10}
        response = self._execute_prompt(http_client, model_settings, "Count from 1 to 100")
        assert response.status_code == 200
        result = response.json()
        # Response should be short due to token limit
        assert len(result["data"].split()) <= 15  # Some buffer for tokenization differences

    def test_top_p(self, http_client):
        """Test top_p parameter (0-1)."""
        model_settings = {"top_p": 0.5}
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 200

        model_settings = {"top_p": 0.95}
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 200

    def test_frequency_penalty(self, http_client):
        """Test frequency_penalty parameter (-2 to 2)."""
        model_settings = {"frequency_penalty": 1.5}
        response = self._execute_prompt(http_client, model_settings, "Repeat the word 'hello' five times")
        assert response.status_code == 200

    def test_presence_penalty(self, http_client):
        """Test presence_penalty parameter (-2 to 2)."""
        model_settings = {"presence_penalty": 1.5}
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 200

    def test_stop_sequences(self, http_client):
        """Test stop_sequences parameter."""
        model_settings = {"stop_sequences": [".", "!"]}
        response = self._execute_prompt(http_client, model_settings, "Tell me a long story")
        assert response.status_code == 200
        result = response.json()
        # Should stop at first sentence
        assert result["data"].count(".") <= 1 or result["data"].count("!") <= 1

    def test_seed(self, http_client):
        """Test seed parameter for reproducibility."""
        model_settings = {"seed": 42, "temperature": 0.7}
        
        # Make two requests with same seed
        response1 = self._execute_prompt(http_client, model_settings, "Generate a random number")
        response2 = self._execute_prompt(http_client, model_settings, "Generate a random number")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # With same seed, responses should be identical
        result1 = response1.json()
        result2 = response2.json()
        assert result1["data"] == result2["data"]

    def test_timeout(self, http_client):
        """Test timeout parameter."""
        model_settings = {"timeout": 60.0}
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 200

    # BudEcosystem-Specific Parameters Tests

    def test_max_completion_tokens(self, http_client):
        """Test max_completion_tokens parameter (alternative to max_tokens)."""
        model_settings = {"max_completion_tokens": 15}
        response = self._execute_prompt(http_client, model_settings, "Count from 1 to 100")
        assert response.status_code == 200
        result = response.json()
        # Response should be short due to token limit
        assert len(result["data"].split()) <= 20  # Some buffer for tokenization

    def test_stream_options(self, http_client):
        """Test stream_options parameter with streaming enabled."""
        model_settings = {"stream_options": {"include_usage": True}}
        
        # Use httpx.stream for streaming response
        request_data = {
            "deployment_name": self.deployment_name,
            "system_prompt": "You are a helpful assistant. Respond briefly.",
            "output_schema": {"type": "object", "properties": {"content": {"type": "string"}}},
            "input_data": "Hello",
            "model_settings": model_settings,
            "stream": True  # Enable streaming as required by stream_options
        }
        
        with httpx.stream("POST", f"{self.base_url}/prompt/execute", 
                         json=request_data, 
                         headers={"Content-Type": "application/json"}, 
                         timeout=30.0) as response:
            assert response.status_code == 200
            
            # Verify we get streaming chunks
            chunks = []
            for chunk in response.iter_text():
                if chunk.strip():
                    chunks.append(chunk)
            
            assert len(chunks) > 0  # Should receive chunks with usage info

    def test_response_format(self, http_client):
        """Test response_format parameter."""
        model_settings = {"response_format": {"type": "json_object"}}
        response = self._execute_prompt(http_client, model_settings, "Return a JSON object with name and age")
        assert response.status_code == 200

    @pytest.mark.skip(reason="tool_choice requires tools to be defined per BudInference API")
    def test_tool_choice(self, http_client):
        """Test tool_choice parameter.
        
        Note: This test can be enabled once tools support is implemented.
        Example usage would be:
        response = self._execute_prompt(
            http_client, 
            model_settings, 
            tools=[{"type": "function", "function": {...}}]
        )
        """
        model_settings = {"tool_choice": "auto"}
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 200

    def test_chat_template(self, http_client):
        """Test chat_template parameter."""
        model_settings = {"chat_template": "default"}
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 200

    def test_chat_template_kwargs(self, http_client):
        """Test chat_template_kwargs parameter."""
        model_settings = {"chat_template_kwargs": {"enable_thinking": True}}
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 200

    def test_mm_processor_kwargs(self, http_client):
        """Test mm_processor_kwargs parameter."""
        model_settings = {"mm_processor_kwargs": {"max_image_size": 1024}}
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 200

    def test_guided_json(self, http_client):
        """Test guided_json parameter for structured generation."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name", "age"]
        }
        model_settings = {"guided_json": schema}
        response = self._execute_prompt(http_client, model_settings, "John is 30 years old")
        assert response.status_code == 200

    def test_guided_regex(self, http_client):
        """Test guided_regex parameter."""
        model_settings = {"guided_regex": r"\d{3}-\d{3}-\d{4}"}
        response = self._execute_prompt(http_client, model_settings, "Generate a phone number")
        assert response.status_code == 200

    def test_guided_choice(self, http_client):
        """Test guided_choice parameter."""
        model_settings = {"guided_choice": ["yes", "no", "maybe"]}
        response = self._execute_prompt(http_client, model_settings, "Is the sky blue?")
        assert response.status_code == 200

    @pytest.mark.skip(reason="guided_grammar returns 503 from BudInference API")
    def test_guided_grammar(self, http_client):
        """Test guided_grammar parameter."""
        model_settings = {"guided_grammar": "root ::= 'yes' | 'no'"}
        response = self._execute_prompt(http_client, model_settings, "Is 2+2=4?")
        assert response.status_code == 200

    @pytest.mark.skip(reason="structural_tag returns 503 from BudInference API")
    def test_structural_tag(self, http_client):
        """Test structural_tag parameter."""
        model_settings = {"structural_tag": "json"}
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 200

    @pytest.mark.skip(reason="guided_decoding_backend returns 503 from BudInference API")
    def test_guided_decoding_backend(self, http_client):
        """Test guided_decoding_backend parameter."""
        model_settings = {"guided_decoding_backend": "outlines"}
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 200

    @pytest.mark.skip(reason="guided_whitespace_pattern returns 503 from BudInference API")
    def test_guided_whitespace_pattern(self, http_client):
        """Test guided_whitespace_pattern parameter."""
        model_settings = {"guided_whitespace_pattern": r"\s*"}
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 200

    # Combination Tests

    def test_multiple_standard_params(self, http_client):
        """Test multiple standard parameters together."""
        model_settings = {
            "temperature": 0.7,
            "max_tokens": 50,
            "top_p": 0.9,
            "frequency_penalty": 0.5,
            "presence_penalty": 0.5,
            "seed": 12345
        }
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 200

    def test_mixed_standard_and_bud_params(self, http_client):
        """Test mix of standard and BudEcosystem parameters."""
        model_settings = {
            "temperature": 0.5,
            "max_tokens": 100,
            "guided_choice": ["positive", "negative", "neutral"],
            "chat_template_kwargs": {"enable_thinking": False}
        }
        response = self._execute_prompt(http_client, model_settings, "What's the sentiment of: 'I love this!'")
        assert response.status_code == 200

    def test_guided_json_with_standard_params(self, http_client):
        """Test guided_json with other parameters."""
        schema = {
            "type": "object",
            "properties": {
                "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1}
            },
            "required": ["sentiment", "confidence"]
        }
        model_settings = {
            "temperature": 0.3,
            "guided_json": schema,
            "seed": 42
        }
        response = self._execute_prompt(http_client, model_settings, "Analyze: 'This product is amazing!'")
        assert response.status_code == 200

    # Edge Cases

    def test_empty_model_settings(self, http_client):
        """Test with empty model settings (should use defaults)."""
        model_settings = {}
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 200

    def test_extreme_temperature_values(self, http_client):
        """Test temperature at extreme values."""
        # Minimum temperature
        model_settings = {"temperature": 0.0}
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 200

        # Maximum temperature
        model_settings = {"temperature": 2.0}
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 200

    def test_conflicting_token_limits(self, http_client):
        """Test when both max_tokens and max_completion_tokens are specified."""
        model_settings = {
            "max_tokens": 50,
            "max_completion_tokens": 100  # Should this override or error?
        }
        response = self._execute_prompt(http_client, model_settings)
        # API should handle this gracefully
        assert response.status_code in [200, 400]  # Either success or validation error

    def test_invalid_parameter_values(self, http_client):
        """Test with invalid parameter values."""
        # Temperature too high
        model_settings = {"temperature": 3.0}
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 422  # Validation error

        # Negative max_tokens
        model_settings = {"max_tokens": -10}
        response = self._execute_prompt(http_client, model_settings)
        assert response.status_code == 422  # Validation error

    # Streaming Tests (requires different endpoint)

    def test_streaming_with_model_params(self, http_client):
        """Test model parameters work with streaming."""
        class OutputSchema(BaseModel):
            content: str

        request_data = {
            "deployment_name": self.deployment_name,
            "system_prompt": "You are a helpful assistant.",
            "output_schema": OutputSchema.model_json_schema(),
            "input_data": "Count from 1 to 5",
            "stream": True,
            "model_settings": {
                "temperature": 0.5,
                "max_tokens": 50,
                "guided_choice": None  # Ensure guided params work with streaming
            }
        }

        with httpx.stream("POST", f"{self.base_url}/prompt/execute", 
                         json=request_data, 
                         headers={"Content-Type": "application/json"}, 
                         timeout=30.0) as response:
            assert response.status_code == 200
            
            # Verify we get streaming chunks
            chunks = []
            for chunk in response.iter_text():
                if chunk.strip():
                    chunks.append(chunk)
            
            assert len(chunks) > 0  # Should receive multiple chunks

# docker exec budserve-development-budprompt pytest tests/test_model_parameters.py -v