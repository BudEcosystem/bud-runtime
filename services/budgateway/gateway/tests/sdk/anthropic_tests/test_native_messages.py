"""Test native Anthropic Messages API with TensorZero using /v1/messages endpoint."""

import os
import sys
from typing import Any, Dict

import pytest
from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import Message, TextBlock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.base_test import BaseChatTest


class TestNativeAnthropicMessages(BaseChatTest):
    """Test native Anthropic Messages API functionality."""
    
    @classmethod
    def get_provider_name(cls) -> str:
        return "anthropic"
    
    @classmethod
    def get_client(cls):
        """Get Anthropic client configured for TensorZero."""
        return Anthropic(
            base_url=cls.base_url,
            api_key=cls.api_key,
            default_headers={"anthropic-version": "2023-06-01"}
        )
    
    def _health_check(self, client):
        """Perform a health check using the client."""
        try:
            client.messages.create(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10
            )
        except Exception as e:
            if "connection" in str(e).lower():
                raise
    
    def create_chat_request(self, **kwargs) -> Dict[str, Any]:
        """Create a chat request in Anthropic's format."""
        request = {
            "model": kwargs.get("model", "claude-3-haiku-20240307"),
            "messages": kwargs.get("messages", []),
            "max_tokens": kwargs.get("max_tokens", 100),
        }
        
        # Add optional parameters
        if "temperature" in kwargs:
            request["temperature"] = kwargs["temperature"]
        if "system" in kwargs:
            request["system"] = kwargs["system"]
        if "stop_sequences" in kwargs:
            request["stop_sequences"] = kwargs["stop_sequences"]
        
        return request
    
    def validate_chat_response(self, response: Any):
        """Validate a chat response."""
        assert isinstance(response, Message)
        assert response.id is not None
        assert response.type == "message"
        assert response.role == "assistant"
        assert len(response.content) > 0
        assert isinstance(response.content[0], TextBlock)
        assert response.content[0].text is not None
        assert response.usage is not None
        assert response.usage.input_tokens > 0
        assert response.usage.output_tokens > 0
    
    def _send_chat_request(self, client, request: Dict[str, Any]):
        """Send a chat request using the client."""
        return client.messages.create(**request)
    
    def test_basic_message_native(self):
        """Test basic message functionality using native Anthropic SDK."""
        client = self.get_client()
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[
                {"role": "user", "content": "Hello from native Anthropic SDK!"}
            ],
            max_tokens=50
        )
        
        self.validate_chat_response(response)
        # For dummy provider, just verify we got a non-empty response
        assert len(response.content[0].text) > 0
        assert response.model == "claude-3-haiku-20240307"
    
    def test_system_prompt_native(self):
        """Test system prompt handling with native SDK."""
        client = self.get_client()
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            system="You are a helpful assistant.",
            messages=[
                {"role": "user", "content": "Test system prompt"}
            ],
            max_tokens=100
        )
        
        self.validate_chat_response(response)
        assert len(response.content[0].text) > 0
    
    def test_multi_turn_conversation_native(self):
        """Test multi-turn conversation with native SDK."""
        client = self.get_client()
        
        messages = [
            {"role": "user", "content": "My name is Bob."},
            {"role": "assistant", "content": "Hello Bob! Nice to meet you."},
            {"role": "user", "content": "What did I tell you?"}
        ]
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=messages,
            max_tokens=100
        )
        
        self.validate_chat_response(response)
        assert len(response.content[0].text) > 0
    
    def test_temperature_parameter_native(self):
        """Test temperature parameter with native SDK."""
        client = self.get_client()
        
        # Test with different temperature values
        for temp in [0.0, 0.5, 1.0]:
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=50,
                temperature=temp
            )
            
            self.validate_chat_response(response)
            assert len(response.content[0].text) > 0
    
    def test_max_tokens_parameter_native(self):
        """Test max_tokens parameter with native SDK."""
        client = self.get_client()
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Tell me about the weather"}],
            max_tokens=20  # Very low limit
        )
        
        self.validate_chat_response(response)
        # For dummy provider, usage might not reflect actual limits
        assert len(response.content[0].text) > 0
    
    def test_multiple_models_native(self):
        """Test different Claude models with native SDK."""
        client = self.get_client()
        
        models = [
            "claude-3-haiku-20240307",
            "claude-3-sonnet-20240229",
            "claude-3-5-sonnet-20241022",
        ]
        
        for model in models:
            response = client.messages.create(
                model=model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=20
            )
            
            self.validate_chat_response(response)
            assert response.model == model
            assert len(response.content[0].text) > 0
    
    def test_stop_sequences_native(self):
        """Test stop sequences with native SDK."""
        client = self.get_client()
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Count: 1, 2, 3, STOP, 4, 5"}],
            max_tokens=100,
            stop_sequences=["STOP"]
        )
        
        self.validate_chat_response(response)
        assert len(response.content[0].text) > 0
    
    @pytest.mark.asyncio
    async def test_async_client_native(self):
        """Test async client functionality with native SDK."""
        client = AsyncAnthropic(
            base_url=self.base_url,
            api_key=self.api_key,
            default_headers={"anthropic-version": "2023-06-01"}
        )
        
        response = await client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Hello async"}],
            max_tokens=50
        )
        
        self.validate_chat_response(response)
        assert len(response.content[0].text) > 0
        
        await client.close()
    
    def test_endpoint_path_verification(self):
        """Verify that requests are going to /v1/messages endpoint."""
        client = self.get_client()
        
        # This test just ensures the client can make a request
        # The actual endpoint verification is done through gateway logs
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Testing endpoint path"}],
            max_tokens=30
        )
        
        self.validate_chat_response(response)
        assert len(response.content[0].text) > 0


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])