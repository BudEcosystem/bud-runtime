"""
CI tests for Together AI models through OpenAI SDK universal compatibility.

These tests use dummy providers and don't require real API keys.
They verify the integration and routing logic works correctly.
"""

import os
import pytest
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuration
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")

# Universal OpenAI client
client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)


class TestTogetherModelsCI:
    """CI tests for Together AI models through OpenAI SDK."""
    
    def test_together_models_routing(self):
        """Test that Together AI model names are properly routed."""
        together_models = [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "meta-llama/Llama-3.2-3B-Instruct-Turbo",
            "meta-llama/Llama-3.1-8B-Instruct-Turbo",
            "Qwen/Qwen2.5-72B-Instruct-Turbo",
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "deepseek-ai/deepseek-v2.5",
        ]
        
        for model in together_models:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=10
            )
            
            # Verify response structure
            assert response.id is not None
            assert response.model == model
            assert response.choices is not None
            assert len(response.choices) == 1
            assert response.choices[0].message.content is not None
    
    def test_together_streaming_ci(self):
        """Test streaming with Together AI models in CI."""
        stream = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
            messages=[{"role": "user", "content": "Test streaming"}],
            max_tokens=50,
            stream=True
        )
        
        chunks_received = 0
        for chunk in stream:
            chunks_received += 1
            assert chunk.id is not None
            assert chunk.model == "meta-llama/Llama-3.1-8B-Instruct-Turbo"
            if chunk.choices[0].delta.content:
                assert isinstance(chunk.choices[0].delta.content, str)
        
        assert chunks_received > 0, "Should receive at least one chunk"
    
    def test_together_special_characters_in_model_names(self):
        """Test that model names with slashes are handled correctly."""
        # Together AI models have slashes in their names
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[{"role": "user", "content": "Test model name parsing"}],
            max_tokens=20
        )
        
        assert response.model == "meta-llama/Llama-3.3-70B-Instruct-Turbo"
        assert "/" in response.model  # Slash should be preserved
    
    def test_cross_provider_compatibility_ci(self):
        """Test OpenAI SDK works uniformly across all providers in CI."""
        test_cases = [
            ("gpt-3.5-turbo", "OpenAI"),
            ("claude-3-haiku-20240307", "Anthropic"),
            ("meta-llama/Llama-3.2-3B-Instruct-Turbo", "Together")
        ]
        
        for model, provider_name in test_cases:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": f"Test {provider_name}"}],
                max_tokens=20
            )
            
            assert response.model == model
            assert response.choices[0].message.content is not None
            # All should have similar response structure
            assert response.usage is not None
            assert response.created is not None
    
    def test_together_model_parameters(self):
        """Test various parameters work with Together AI models."""
        model = "Qwen/Qwen2.5-72B-Instruct-Turbo"
        
        # Test temperature
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=20,
            temperature=0.7
        )
        assert response.choices[0].message.content is not None
        
        # Test max_tokens
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=5
        )
        assert response.choices[0].message.content is not None
        
        # Test system message
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Test"}
            ],
            max_tokens=20
        )
        assert response.choices[0].message.content is not None
    
    def test_together_error_handling(self):
        """Test error handling for invalid requests."""
        # Test with invalid model name
        with pytest.raises(Exception) as exc_info:
            client.chat.completions.create(
                model="invalid-together-model",
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=10
            )
        
        # Should get an error (model not found)
        assert exc_info.value is not None
    
    def test_together_multi_turn_conversation_ci(self):
        """Test multi-turn conversations work correctly."""
        messages = [
            {"role": "user", "content": "My name is Alice"},
            {"role": "assistant", "content": "Hello Alice!"},
            {"role": "user", "content": "What's my name?"}
        ]
        
        response = client.chat.completions.create(
            model="deepseek-ai/deepseek-v2.5",
            messages=messages,
            max_tokens=30
        )
        
        assert response.choices[0].message.content is not None
        assert response.choices[0].message.role == "assistant"
    
    def test_together_json_response_structure(self):
        """Test the response structure matches OpenAI format."""
        response = client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=[{"role": "user", "content": "Test response format"}],
            max_tokens=20
        )
        
        # Check OpenAI response structure
        assert hasattr(response, 'id')
        assert hasattr(response, 'object')
        assert response.object == "chat.completion"
        assert hasattr(response, 'created')
        assert hasattr(response, 'model')
        assert hasattr(response, 'choices')
        assert hasattr(response, 'usage')
        
        # Check choice structure
        choice = response.choices[0]
        assert hasattr(choice, 'index')
        assert hasattr(choice, 'message')
        assert hasattr(choice, 'finish_reason')
        
        # Check message structure
        message = choice.message
        assert hasattr(message, 'role')
        assert message.role == "assistant"
        assert hasattr(message, 'content')
        
        # Check usage structure
        assert hasattr(response.usage, 'prompt_tokens')
        assert hasattr(response.usage, 'completion_tokens')
        assert hasattr(response.usage, 'total_tokens')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])