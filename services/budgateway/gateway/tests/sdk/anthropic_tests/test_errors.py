"""Test error handling with Anthropic SDK and TensorZero."""

import os
import sys

import pytest
from anthropic import Anthropic, APIError, APIStatusError
from anthropic.types import Message

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.base_test import BaseSDKTest


class TestAnthropicErrors(BaseSDKTest):
    """Test error handling scenarios."""
    
    @classmethod
    def get_provider_name(cls) -> str:
        return "anthropic"
    
    @classmethod
    def get_client(cls):
        return Anthropic(
            base_url=cls.base_url,
            api_key=cls.api_key,
            default_headers={"anthropic-version": "2023-06-01"}
        )
    
    def _health_check(self, client):
        """Perform a health check using the client."""
        client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=10
        )
    
    def test_invalid_model(self):
        """Test with invalid model name."""
        client = self.get_client()
        
        with pytest.raises(APIError) as exc_info:
            client.messages.create(
                model="invalid-model-name",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=50
            )
        
        # Should get a model not found error
        error_str = str(exc_info.value).lower()
        assert "model" in error_str or "not found" in error_str
    
    def test_missing_required_params(self):
        """Test missing required parameters."""
        client = self.get_client()
        
        # Missing max_tokens (required for Anthropic)
        # This should raise TypeError from SDK validation before making request
        with pytest.raises(TypeError) as exc_info:
            client.messages.create(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": "Hello"}]
                # max_tokens is missing
            )
        
        # The SDK should catch this before sending
        error_str = str(exc_info.value).lower()
        assert "max_tokens" in error_str or "required" in error_str
    
    def test_invalid_message_format(self):
        """Test invalid message format."""
        client = self.get_client()
        
        # Test with invalid role - should get APIStatusError from gateway
        with pytest.raises(APIStatusError) as exc_info:
            client.messages.create(
                model="claude-3-haiku-20240307",
                messages=[{"role": "system", "content": "You are helpful"}],  # system role not allowed in messages
                max_tokens=50
            )
        
        # Should get validation error with 400 status
        assert exc_info.value.status_code == 400
        error_str = str(exc_info.value).lower()
        assert "role" in error_str or "system" in error_str or "invalid" in error_str
    
    def test_empty_messages(self):
        """Test with empty messages array."""
        client = self.get_client()
        
        with pytest.raises(APIStatusError) as exc_info:
            client.messages.create(
                model="claude-3-haiku-20240307",
                messages=[],
                max_tokens=50
            )
        
        # Should get validation error with 400 status
        assert exc_info.value.status_code == 400
        error_str = str(exc_info.value).lower()
        assert "message" in error_str or "empty" in error_str or "required" in error_str
    
    def test_token_limit_exceeded(self):
        """Test exceeding token limits."""
        client = self.get_client()
        
        # Try to request way too many tokens
        with pytest.raises(APIError) as exc_info:
            client.messages.create(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=1000000  # Way over any model's limit
            )
        
        error_str = str(exc_info.value).lower()
        assert "token" in error_str or "limit" in error_str or "max" in error_str
    
    def test_invalid_temperature(self):
        """Test with invalid temperature values."""
        client = self.get_client()
        
        # Temperature > 1.0
        with pytest.raises(APIError) as exc_info:
            client.messages.create(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=50,
                temperature=2.0  # Invalid: should be 0-1
            )
        
        error_str = str(exc_info.value).lower()
        assert "temperature" in error_str or "invalid" in error_str or "range" in error_str
    
    def test_malformed_tool_schema(self):
        """Test with malformed tool schema."""
        client = self.get_client()
        
        # Invalid tool schema
        tools = [{
            "name": "bad_tool",
            # Missing required fields like description and input_schema
        }]
        
        # Could be ValueError from SDK or APIStatusError from gateway
        with pytest.raises((ValueError, APIStatusError)) as exc_info:
            client.messages.create(
                model="claude-3-5-sonnet-20241022",
                messages=[{"role": "user", "content": "Use the tool"}],
                tools=tools,
                max_tokens=100
            )
        
        # Should get validation error
        error_str = str(exc_info.value).lower()
        assert "tool" in error_str or "schema" in error_str or "invalid" in error_str
    
    def test_rate_limit_headers(self):
        """Test that rate limit information is accessible."""
        client = self.get_client()
        
        # Make a successful request
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        
        assert isinstance(response, Message)
        # Rate limit headers should be available in the response metadata
        # (Implementation depends on how TensorZero exposes these)
    
    def test_streaming_error(self):
        """Test error handling in streaming mode."""
        client = self.get_client()
        
        with pytest.raises(APIError):
            stream = client.messages.create(
                model="invalid-model",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=50,
                stream=True
            )
            
            # Try to consume the stream
            for _ in stream:
                pass
    
    def test_timeout_handling(self):
        """Test timeout handling."""
        # Create client with very short timeout
        client = Anthropic(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=0.001,  # 1ms timeout - should fail
            default_headers={"anthropic-version": "2023-06-01"}
        )
        
        with pytest.raises(Exception) as exc_info:
            client.messages.create(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=50
            )
        
        # Should be a timeout error
        error_str = str(exc_info.value).lower()
        assert "timeout" in error_str or "timed out" in error_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])