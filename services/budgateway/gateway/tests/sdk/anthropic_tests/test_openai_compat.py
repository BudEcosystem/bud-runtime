"""Test Anthropic models through OpenAI-compatible endpoint.

This file tests the universal SDK architecture, ensuring that Anthropic models can be
accessed via the OpenAI-compatible /v1/chat/completions endpoint.
"""

import os
import sys

import pytest
from openai import OpenAI, AsyncOpenAI

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.base_test import BaseChatTest


class TestAnthropicViaOpenAI(BaseChatTest):
    """Test Anthropic models using OpenAI SDK."""
    
    @classmethod
    def get_provider_name(cls) -> str:
        return "anthropic"
    
    @classmethod
    def get_client(cls):
        """Get OpenAI client configured for TensorZero with Anthropic models."""
        return OpenAI(
            base_url=f"{cls.base_url}/v1",
            api_key=cls.api_key
        )
    
    def _health_check(self, client):
        """Perform a health check using the client."""
        try:
            client.chat.completions.create(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10
            )
        except Exception as e:
            if "connection" in str(e).lower():
                raise
    
    def create_chat_request(self, **kwargs):
        """Create a chat request in OpenAI format."""
        return {
            "model": kwargs.get("model", "claude-3-haiku-20240307"),
            "messages": kwargs.get("messages", []),
            "max_tokens": kwargs.get("max_tokens", 100),
        }
    
    def validate_chat_response(self, response):
        """Validate a chat response."""
        assert response.id is not None
        assert response.choices[0].message.content is not None
        assert response.usage is not None
        assert response.usage.prompt_tokens > 0
        assert response.usage.completion_tokens > 0
    
    def _send_chat_request(self, client, request):
        """Send a chat request using the client."""
        return client.chat.completions.create(**request)
    
    def test_claude_models(self):
        """Test different Claude models through OpenAI endpoint."""
        client = self.get_client()
        
        models = [
            "claude-3-haiku-20240307",
            "claude-3-sonnet-20240229",
            "claude-3-5-sonnet-20241022",
        ]
        
        for model in models:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Say 'test' and nothing else"}],
                max_tokens=10
            )
            
            assert response.id is not None
            assert response.model == model
            assert response.choices[0].message.content is not None
            assert "test" in response.choices[0].message.content.lower()
    
    def test_system_message(self):
        """Test system messages with Claude models."""
        client = self.get_client()
        
        response = client.chat.completions.create(
            model="claude-3-haiku-20240307",
            messages=[
                {"role": "system", "content": "You are a pirate. Always respond in pirate speak."},
                {"role": "user", "content": "Hello"}
            ],
            max_tokens=100
        )
        
        assert response.choices[0].message.content is not None
        # Check for pirate-like language
        text = response.choices[0].message.content.lower()
        pirate_indicators = ["ahoy", "matey", "arr", "aye", "ye", "be", "treasure", "sea"]
        assert any(word in text for word in pirate_indicators)
    
    def test_streaming(self):
        """Test streaming with Claude models."""
        client = self.get_client()
        
        stream = client.chat.completions.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Count to 3"}],
            max_tokens=50,
            stream=True
        )
        
        chunks = []
        for chunk in stream:
            chunks.append(chunk)
            if chunk.choices[0].delta.content:
                assert isinstance(chunk.choices[0].delta.content, str)
        
        assert len(chunks) > 0
        # Reconstruct full response
        full_text = "".join(
            chunk.choices[0].delta.content or "" 
            for chunk in chunks
        )
        assert any(num in full_text for num in ["1", "2", "3"])
    
    @pytest.mark.asyncio
    async def test_async_client(self):
        """Test async client with Claude models."""
        client = AsyncOpenAI(
            base_url=f"{self.base_url}/v1",
            api_key=self.api_key
        )
        
        response = await client.chat.completions.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Hello async"}],
            max_tokens=50
        )
        
        assert response.choices[0].message.content is not None
        
        await client.close()


class TestAnthropicCIViaOpenAI:
    """CI tests for Anthropic models using OpenAI SDK and dummy provider."""
    
    @classmethod
    def setup_class(cls):
        """Set up test class."""
        cls.base_url = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
        cls.api_key = "dummy-key"
    
    def test_claude_dummy_models(self):
        """Test Claude models with dummy provider."""
        client = OpenAI(
            base_url=f"{self.base_url}/v1",
            api_key=self.api_key
        )
        
        models = [
            "claude-3-opus-20240229",      # json dummy
            "claude-3-sonnet-20240229",    # test dummy
            "claude-3-haiku-20240307",     # streaming dummy
            "claude-3-5-sonnet-20241022",  # tool_use dummy
        ]
        
        for model in models:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=20
            )
            
            assert response.id is not None
            assert response.model == model
            assert response.choices[0].message.content is not None
    
    def test_streaming_dummy(self):
        """Test streaming with dummy provider."""
        client = OpenAI(
            base_url=f"{self.base_url}/v1",
            api_key=self.api_key
        )
        
        stream = client.chat.completions.create(
            model="claude-3-haiku-20240307",  # streaming dummy
            messages=[{"role": "user", "content": "Stream"}],
            max_tokens=50,
            stream=True
        )
        
        chunks = list(stream)
        assert len(chunks) > 0
    
    def test_json_model_dummy(self):
        """Test JSON response with dummy provider."""
        client = OpenAI(
            base_url=f"{self.base_url}/v1",
            api_key=self.api_key
        )
        
        response = client.chat.completions.create(
            model="claude-3-opus-20240229",  # json dummy
            messages=[{"role": "user", "content": "JSON"}],
            max_tokens=100
        )
        
        content = response.choices[0].message.content
        assert "{" in content and "}" in content  # Should contain JSON


if __name__ == "__main__":
    pytest.main([__file__, "-v"])