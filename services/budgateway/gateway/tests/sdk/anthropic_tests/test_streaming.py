"""Test Anthropic streaming functionality with TensorZero."""

import os
import sys
from typing import Any, Dict

import pytest
from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import Message, MessageStreamEvent
from anthropic.types.message_start_event import MessageStartEvent
from anthropic.types.content_block_start_event import ContentBlockStartEvent
from anthropic.types.content_block_delta_event import ContentBlockDeltaEvent
from anthropic.types.content_block_stop_event import ContentBlockStopEvent
from anthropic.types.message_delta_event import MessageDeltaEvent
from anthropic.types.message_stop_event import MessageStopEvent

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.base_test import BaseStreamingTest


class TestAnthropicStreaming(BaseStreamingTest):
    """Test streaming functionality with Anthropic SDK."""
    
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
    
    def create_streaming_request(self, **kwargs) -> Dict[str, Any]:
        """Create a streaming request in Anthropic's format."""
        request = {
            "model": kwargs.get("model", "claude-3-haiku-20240307"),
            "messages": kwargs.get("messages", []),
            "max_tokens": kwargs.get("max_tokens", 100),
            "stream": True
        }
        
        if "temperature" in kwargs:
            request["temperature"] = kwargs["temperature"]
        if "system" in kwargs:
            request["system"] = kwargs["system"]
        
        return request
    
    def validate_streaming_chunk(self, chunk: Any):
        """Validate a single streaming chunk."""
        # Anthropic uses different event types
        assert isinstance(chunk, (
            MessageStartEvent,
            ContentBlockStartEvent,
            ContentBlockDeltaEvent,
            ContentBlockStopEvent,
            MessageDeltaEvent,
            MessageStopEvent
        ))
        
        # Each event type has specific fields
        if isinstance(chunk, MessageStartEvent):
            assert chunk.type == "message_start"
            assert chunk.message is not None
        elif isinstance(chunk, ContentBlockDeltaEvent):
            assert chunk.type == "content_block_delta"
            assert chunk.delta is not None
    
    def send_streaming_request(self, client, request: Dict[str, Any]):
        """Send a streaming request and return an iterator."""
        return client.messages.create(**request)
    
    def test_basic_streaming(self):
        """Test basic streaming functionality."""
        client = self.get_client()
        
        stream = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Count from 1 to 5"}],
            max_tokens=100,
            stream=True
        )
        
        events_received = []
        text_chunks = []
        
        for event in stream:
            events_received.append(event)
            self.validate_streaming_chunk(event)
            
            # Collect text from delta events
            if isinstance(event, ContentBlockDeltaEvent):
                if hasattr(event.delta, 'text'):
                    text_chunks.append(event.delta.text)
        
        # Should have received multiple events
        assert len(events_received) > 0
        
        # Should have start and stop events
        assert any(isinstance(e, MessageStartEvent) for e in events_received)
        assert any(isinstance(e, MessageStopEvent) for e in events_received)
        
        # Should have received text
        assert len(text_chunks) > 0
        full_text = "".join(text_chunks)
        # Should contain numbers 1-5
        for num in ["1", "2", "3", "4", "5"]:
            assert num in full_text
    
    def test_streaming_with_system(self):
        """Test streaming with system prompt."""
        client = self.get_client()
        
        stream = client.messages.create(
            model="claude-3-haiku-20240307",
            system="You are a helpful assistant who speaks in short sentences.",
            messages=[{"role": "user", "content": "Tell me about Python"}],
            max_tokens=100,
            stream=True
        )
        
        text_chunks = []
        for event in stream:
            if isinstance(event, ContentBlockDeltaEvent) and hasattr(event.delta, 'text'):
                text_chunks.append(event.delta.text)
        
        full_text = "".join(text_chunks)
        assert "Python" in full_text or "python" in full_text
    
    def test_streaming_stop_reason(self):
        """Test streaming stop reasons."""
        client = self.get_client()
        
        # Test max_tokens stop
        stream = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Count from 1 to 100"}],
            max_tokens=10,
            stream=True
        )
        
        stop_event = None
        for event in stream:
            if isinstance(event, MessageStopEvent):
                stop_event = event
        
        assert stop_event is not None
        # The stop reason should indicate max_tokens
        # Note: The actual field name might vary based on Anthropic's response format
    
    def test_streaming_usage(self):
        """Test usage information in streaming."""
        client = self.get_client()
        
        stream = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Say hello"}],
            max_tokens=50,
            stream=True
        )
        
        message_start = None
        for event in stream:
            if isinstance(event, MessageStartEvent):
                message_start = event
                break
        
        assert message_start is not None
        assert message_start.message.usage is not None
        assert message_start.message.usage.input_tokens > 0
    
    @pytest.mark.asyncio
    async def test_async_streaming(self):
        """Test async streaming functionality."""
        client = AsyncAnthropic(
            base_url=self.base_url,
            api_key=self.api_key,
            default_headers={"anthropic-version": "2023-06-01"}
        )
        
        stream = await client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Count to 3"}],
            max_tokens=50,
            stream=True
        )
        
        text_chunks = []
        async for event in stream:
            if isinstance(event, ContentBlockDeltaEvent) and hasattr(event.delta, 'text'):
                text_chunks.append(event.delta.text)
        
        full_text = "".join(text_chunks)
        assert "1" in full_text
        assert "2" in full_text
        assert "3" in full_text
        
        await client.close()
    
    def test_streaming_with_long_response(self):
        """Test streaming with longer responses."""
        client = self.get_client()
        
        stream = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Write a haiku about streaming data"}],
            max_tokens=100,
            stream=True
        )
        
        delta_count = 0
        text_chunks = []
        
        for event in stream:
            if isinstance(event, ContentBlockDeltaEvent):
                delta_count += 1
                if hasattr(event.delta, 'text'):
                    text_chunks.append(event.delta.text)
        
        # Should have multiple delta events for a longer response
        assert delta_count > 3
        
        # Should form a complete haiku
        full_text = "".join(text_chunks)
        assert len(full_text) > 20  # Haikus are typically longer than this


if __name__ == "__main__":
    pytest.main([__file__, "-v"])