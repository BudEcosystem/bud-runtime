"""
CI-friendly chat endpoint tests using dummy providers.
These tests are adapted to work with the dummy provider's behavior.
"""

import os
import pytest
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuration for CI
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")

# Client configured for dummy provider testing
tensorzero_client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)


class TestChatCompletionsCI:
    """Test chat completions with dummy provider"""

    def test_basic_chat_completion(self):
        """Test basic chat completion"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"}
        ]
        
        response = tensorzero_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        
        # Check response structure
        assert response.id
        assert response.object == "chat.completion"
        assert response.created
        assert response.model == "gpt-3.5-turbo"
        assert len(response.choices) == 1
        assert response.choices[0].index == 0
        assert response.choices[0].finish_reason == "stop"
        
        # Dummy provider with json model returns {"answer":"Hello"}
        content = response.choices[0].message.content
        assert content
        assert isinstance(content, str)
        # For json model, content should be JSON
        if "answer" in content:
            assert '{"answer":"Hello"}' == content

    def test_multiple_messages(self):
        """Test chat with multiple messages"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What's 2+2?"},
            {"role": "assistant", "content": "2+2 equals 4."},
            {"role": "user", "content": "What's 3+3?"}
        ]
        
        response = tensorzero_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        
        assert response.choices[0].message.content
        assert response.choices[0].message.role == "assistant"

    def test_streaming_chat_completion(self):
        """Test streaming chat completion"""
        messages = [{"role": "user", "content": "Count to three"}]
        
        stream = tensorzero_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            stream=True
        )
        
        chunks = list(stream)
        assert len(chunks) > 0
        
        # First chunk should have role
        assert chunks[0].choices[0].delta.role == "assistant"
        
        # Collect all content
        content = "".join(
            chunk.choices[0].delta.content or ""
            for chunk in chunks
        )
        assert content

    def test_completion_parameters(self):
        """Test various completion parameters"""
        messages = [{"role": "user", "content": "Test"}]
        
        # These parameters are accepted but may not affect dummy provider
        response = tensorzero_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=50,
            top_p=0.9,
            frequency_penalty=0.5,
            presence_penalty=0.5
            # Note: n > 1 is not supported by TensorZero's OpenAI-compatible endpoint
        )
        
        assert response.choices
        assert len(response.choices) == 1
        
    def test_different_models(self):
        """Test different model configurations"""
        messages = [{"role": "user", "content": "Hello"}]
        
        # Test gpt-4 (configured with model_name="test")
        response = tensorzero_client.chat.completions.create(
            model="gpt-4",
            messages=messages
        )
        
        assert response.model == "gpt-4"
        assert response.choices[0].message.content
        # The "test" model returns different content than "json" model
        
    @pytest.mark.asyncio
    async def test_async_chat_completion(self):
        """Test async chat completion"""
        from openai import AsyncOpenAI
        
        async_client = AsyncOpenAI(
            base_url=f"{TENSORZERO_BASE_URL}/v1",
            api_key=TENSORZERO_API_KEY
        )
        
        messages = [{"role": "user", "content": "Test async"}]
        
        response = await async_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        
        assert response.choices[0].message.content
        # Just verify we got a response, don't check specific content

    def test_empty_messages_allowed(self):
        """Test that empty messages are handled by dummy provider"""
        # Dummy provider doesn't validate, so this should work
        response = tensorzero_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[]
        )
        
        # Should still get a response
        assert response.choices[0].message.content

    def test_invalid_model_rejected(self):
        """Test that invalid models are rejected"""
        with pytest.raises(Exception):
            tensorzero_client.chat.completions.create(
                model="invalid-model",
                messages=[{"role": "user", "content": "test"}]
            )


if __name__ == "__main__":
    print("CI chat tests ready to run!")