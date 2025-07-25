"""CI tests for Anthropic SDK using dummy provider."""

import os
import sys

import pytest
from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import Message, TextBlock, ContentBlockDeltaEvent

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAnthropicCI:
    """Test Anthropic SDK with dummy provider (no real API calls)."""
    
    @classmethod
    def setup_class(cls):
        """Set up test class."""
        cls.base_url = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
        cls.api_key = "dummy-key"  # Dummy provider doesn't validate keys
    
    def test_basic_message_dummy(self):
        """Test basic message with dummy provider."""
        client = Anthropic(
            base_url=self.base_url,
            api_key=self.api_key
        )
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=50
        )
        
        assert isinstance(response, Message)
        assert response.id is not None
        assert response.role == "assistant"
        assert len(response.content) > 0
        assert isinstance(response.content[0], TextBlock)
        assert response.content[0].text is not None
    
    def test_json_response_model(self):
        """Test model configured for JSON responses."""
        client = Anthropic(
            base_url=self.base_url,
            api_key=self.api_key
        )
        
        response = client.messages.create(
            model="claude-3-opus-20240229",  # Configured with json dummy
            messages=[{"role": "user", "content": "Return JSON"}],
            max_tokens=100
        )
        
        assert isinstance(response, Message)
        # Dummy provider with json model returns predictable JSON
        text = response.content[0].text
        assert "{" in text and "}" in text  # Should contain JSON
    
    def test_streaming_dummy(self):
        """Test streaming with dummy provider."""
        client = Anthropic(
            base_url=self.base_url,
            api_key=self.api_key
        )
        
        stream = client.messages.create(
            model="claude-3-haiku-20240307",  # Configured for streaming
            messages=[{"role": "user", "content": "Stream this"}],
            max_tokens=50,
            stream=True
        )
        
        chunks_received = 0
        text_chunks = []
        
        for event in stream:
            chunks_received += 1
            if isinstance(event, ContentBlockDeltaEvent) and hasattr(event.delta, 'text'):
                text_chunks.append(event.delta.text)
        
        assert chunks_received > 0
        assert len(text_chunks) > 0
        
        # Dummy provider should return predictable content
        full_text = "".join(text_chunks)
        assert len(full_text) > 0
    
    def test_tool_use_dummy(self):
        """Test tool use with dummy provider."""
        client = Anthropic(
            base_url=self.base_url,
            api_key=self.api_key
        )
        
        tools = [{
            "name": "test_tool",
            "description": "A test tool",
            "input_schema": {
                "type": "object",
                "properties": {
                    "param": {"type": "string"}
                },
                "required": ["param"]
            }
        }]
        
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",  # Configured for tool_use dummy
            messages=[{"role": "user", "content": "Use the tool"}],
            tools=tools,
            max_tokens=200
        )
        
        assert isinstance(response, Message)
        # Dummy provider with tool_use model might return tool calls
        # or just text mentioning tools
    
    def test_system_prompt_dummy(self):
        """Test system prompt with dummy provider."""
        client = Anthropic(
            base_url=self.base_url,
            api_key=self.api_key
        )
        
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            system="You are a test assistant",
            messages=[{"role": "user", "content": "Who are you?"}],
            max_tokens=50
        )
        
        assert isinstance(response, Message)
        # Dummy provider should return some response
        assert len(response.content[0].text) > 0
    
    def test_multi_turn_dummy(self):
        """Test multi-turn conversation with dummy provider."""
        client = Anthropic(
            base_url=self.base_url,
            api_key=self.api_key
        )
        
        messages = [
            {"role": "user", "content": "My name is Test"},
            {"role": "assistant", "content": "Nice to meet you, Test"},
            {"role": "user", "content": "What's my name?"}
        ]
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=messages,
            max_tokens=50
        )
        
        assert isinstance(response, Message)
        # Dummy should handle multi-turn
        assert response.content[0].text is not None
    
    @pytest.mark.asyncio
    async def test_async_dummy(self):
        """Test async client with dummy provider."""
        client = AsyncAnthropic(
            base_url=self.base_url,
            api_key=self.api_key
        )
        
        response = await client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Async test"}],
            max_tokens=50
        )
        
        assert isinstance(response, Message)
        assert response.content[0].text is not None
        
        await client.close()
    
    def test_all_models_dummy(self):
        """Test all configured dummy models."""
        client = Anthropic(
            base_url=self.base_url,
            api_key=self.api_key
        )
        
        models = [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-2.1",
            "claude-instant-1.2"
        ]
        
        for model in models:
            response = client.messages.create(
                model=model,
                messages=[{"role": "user", "content": f"Test {model}"}],
                max_tokens=20
            )
            
            assert isinstance(response, Message)
            assert response.model == model
            assert response.content[0].text is not None
    
    def test_error_handling_dummy(self):
        """Test error scenarios with dummy provider."""
        client = Anthropic(
            base_url=self.base_url,
            api_key=self.api_key
        )
        
        # Test with non-existent model
        with pytest.raises(Exception):
            client.messages.create(
                model="non-existent-model",
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=50
            )
    
    def test_usage_tracking_dummy(self):
        """Test usage information with dummy provider."""
        client = Anthropic(
            base_url=self.base_url,
            api_key=self.api_key
        )
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Track usage"}],
            max_tokens=50
        )
        
        assert response.usage is not None
        assert response.usage.input_tokens > 0
        assert response.usage.output_tokens > 0
        
        # Dummy provider returns predictable token counts
        total = response.usage.input_tokens + response.usage.output_tokens
        assert total > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])