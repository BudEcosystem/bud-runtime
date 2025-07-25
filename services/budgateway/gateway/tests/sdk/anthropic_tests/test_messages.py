"""Test Anthropic Messages API compatibility with TensorZero."""

import os
import sys
from typing import Any, Dict, List

import pytest
from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import Message, ContentBlock, TextBlock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.base_test import BaseChatTest, BaseAuthTest
from common.utils import TestDataGenerator, wait_for_health_check


class TestAnthropicMessages(BaseChatTest):
    """Test basic Messages API functionality."""
    
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
        # Try a simple message request
        try:
            client.messages.create(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10
            )
        except Exception as e:
            # Check if it's a connection error vs other errors
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
    
    def test_basic_message(self):
        """Test basic message functionality."""
        client = self.get_client()
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[
                {"role": "user", "content": "Say 'Hello, TensorZero!' and nothing else."}
            ],
            max_tokens=50
        )
        
        self.validate_chat_response(response)
        # For dummy provider, just verify we got a non-empty response
        assert len(response.content[0].text) > 0
    
    def test_system_prompt(self):
        """Test system prompt handling."""
        client = self.get_client()
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            system="You are a pirate. Always respond in pirate speak.",
            messages=[
                {"role": "user", "content": "Hello"}
            ],
            max_tokens=100
        )
        
        self.validate_chat_response(response)
        # For dummy provider, just verify we got a non-empty response with system prompt handled
        assert len(response.content[0].text) > 0
    
    def test_multi_turn_conversation(self):
        """Test multi-turn conversation."""
        client = self.get_client()
        
        messages = [
            {"role": "user", "content": "My name is Alice. Remember it."},
            {"role": "assistant", "content": "I'll remember that your name is Alice."},
            {"role": "user", "content": "What's my name?"}
        ]
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=messages,
            max_tokens=100
        )
        
        self.validate_chat_response(response)
        # For dummy provider, just verify we got a non-empty response
        assert len(response.content[0].text) > 0
    
    def test_temperature_variation(self):
        """Test temperature parameter."""
        client = self.get_client()
        
        # Low temperature (more deterministic)
        response1 = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "What is 2+2?"}],
            max_tokens=50,
            temperature=0.0
        )
        
        # High temperature (more random)
        response2 = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "What is 2+2?"}],
            max_tokens=50,
            temperature=1.0
        )
        
        self.validate_chat_response(response1)
        self.validate_chat_response(response2)
        
        # Both should mention 4, but might have different phrasing
        assert "4" in response1.content[0].text
        assert "4" in response2.content[0].text
    
    def test_max_tokens_limit(self):
        """Test max_tokens parameter."""
        client = self.get_client()
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Count from 1 to 100"}],
            max_tokens=10  # Very low limit
        )
        
        self.validate_chat_response(response)
        # Response should be truncated
        assert response.stop_reason == "max_tokens"
        assert response.usage.output_tokens <= 10
    
    def test_different_models(self):
        """Test different Claude models."""
        client = self.get_client()
        
        models = [
            "claude-3-haiku-20240307",
            "claude-3-sonnet-20240229",
            "claude-3-5-sonnet-20241022",
        ]
        
        for model in models:
            response = client.messages.create(
                model=model,
                messages=[{"role": "user", "content": "Say 'test'"}],
                max_tokens=10
            )
            
            self.validate_chat_response(response)
            assert response.model == model
    
    @pytest.mark.asyncio
    async def test_async_client(self):
        """Test async client functionality."""
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
        
        await client.close()
    
    def test_stop_sequences(self):
        """Test stop sequences."""
        client = self.get_client()
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Count: 1, 2, 3, STOP, 4, 5"}],
            max_tokens=100,
            stop_sequences=["STOP"]
        )
        
        self.validate_chat_response(response)
        # Response should stop before "STOP"
        assert "STOP" not in response.content[0].text
        assert "4" not in response.content[0].text
        assert "5" not in response.content[0].text


class TestAnthropicAuth(BaseAuthTest):
    """Test authentication with Anthropic SDK."""
    
    @classmethod
    def get_provider_name(cls) -> str:
        return "anthropic"
    
    @classmethod
    def get_client(cls):
        return Anthropic(
            base_url=cls.base_url,
            api_key=cls.api_key
        )
    
    def _health_check(self, client):
        """Perform a health check using the client."""
        client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=10
        )
    
    def create_client_with_auth(self, api_key: str):
        """Create a client with specific authentication."""
        return Anthropic(
            base_url=self.base_url,
            api_key=api_key
        )
    
    def validate_auth_error(self, error: Exception):
        """Validate that the error is an authentication error."""
        error_str = str(error).lower()
        # Anthropic SDK might wrap the error differently
        assert any(word in error_str for word in ["auth", "unauthorized", "forbidden", "401", "403"])


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])