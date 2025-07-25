"""Test Anthropic content types and advanced features with TensorZero."""

import json
import os
import sys
from typing import Any, Dict

import pytest
from anthropic import Anthropic
from anthropic.types import Message, TextBlock, ToolUseBlock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.base_test import BaseSDKTest


class TestAnthropicContentTypes(BaseSDKTest):
    """Test different content types and advanced features."""
    
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
    
    def test_multimodal_text_only(self):
        """Test content blocks with text only."""
        client = self.get_client()
        
        # Anthropic supports content as a list of blocks
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "text", "text": " World!"}
                ]
            }],
            max_tokens=50
        )
        
        assert isinstance(response, Message)
        assert len(response.content) > 0
        assert isinstance(response.content[0], TextBlock)
    
    def test_tool_use(self):
        """Test tool use functionality."""
        client = self.get_client()
        
        tools = [{
            "name": "get_weather",
            "description": "Get the current weather in a given location",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "The unit for temperature"
                    }
                },
                "required": ["location"]
            }
        }]
        
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",  # Tool use works best with newer models
            messages=[{
                "role": "user",
                "content": "What's the weather like in New York?"
            }],
            tools=tools,
            max_tokens=200
        )
        
        assert isinstance(response, Message)
        # Response might contain tool use blocks
        has_tool_use = any(isinstance(block, ToolUseBlock) for block in response.content)
        if has_tool_use:
            tool_block = next(block for block in response.content if isinstance(block, ToolUseBlock))
            assert tool_block.name == "get_weather"
            assert "location" in tool_block.input
    
    def test_tool_use_with_response(self):
        """Test tool use with tool response."""
        client = self.get_client()
        
        tools = [{
            "name": "calculate",
            "description": "Perform basic arithmetic calculations",
            "input_schema": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The mathematical expression to evaluate"
                    }
                },
                "required": ["expression"]
            }
        }]
        
        # First message asking to use the tool
        messages = [{
            "role": "user",
            "content": "What is 15 * 37?"
        }]
        
        response1 = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            messages=messages,
            tools=tools,
            max_tokens=200
        )
        
        # If the model used a tool, we can simulate the tool response
        if any(isinstance(block, ToolUseBlock) for block in response1.content):
            tool_block = next(block for block in response1.content if isinstance(block, ToolUseBlock))
            
            # Add assistant's tool use to conversation
            messages.append({
                "role": "assistant",
                "content": response1.content
            })
            
            # Add tool result
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": "555"  # 15 * 37 = 555
                }]
            })
            
            # Get final response
            response2 = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                messages=messages,
                max_tokens=200
            )
            
            assert isinstance(response2, Message)
            # Response should mention the result
            full_text = "".join(block.text for block in response2.content if isinstance(block, TextBlock))
            assert "555" in full_text
    
    def test_json_mode(self):
        """Test requesting JSON output."""
        client = self.get_client()
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=[{
                "role": "user",
                "content": "Return a JSON object with name='test' and value=123. Only return valid JSON."
            }],
            max_tokens=100
        )
        
        assert isinstance(response, Message)
        text = response.content[0].text.strip()
        
        # Try to parse as JSON
        try:
            data = json.loads(text)
            assert data.get("name") == "test"
            assert data.get("value") == 123
        except json.JSONDecodeError:
            # If model didn't return valid JSON, at least check it tried
            assert "name" in text and "test" in text
            assert "value" in text and "123" in text
    
    def test_multiple_system_messages_behavior(self):
        """Test how system messages are handled."""
        client = self.get_client()
        
        # Anthropic uses a single system parameter, not system messages
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            system="You are a helpful assistant. Always be concise.",
            messages=[
                {"role": "user", "content": "What is Python?"}
            ],
            max_tokens=100
        )
        
        assert isinstance(response, Message)
        # Response should be concise due to system prompt
        text = response.content[0].text
        # A concise response should be relatively short
        assert len(text.split()) < 50  # Less than 50 words
    
    def test_long_context(self):
        """Test handling of long context."""
        client = self.get_client()
        
        # Create a long context
        long_text = "This is a test. " * 100  # ~400 words
        
        messages = [
            {"role": "user", "content": f"Remember this text: {long_text}"},
            {"role": "assistant", "content": "I'll remember the text you provided."},
            {"role": "user", "content": "How many times did I repeat 'This is a test' in my first message?"}
        ]
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            messages=messages,
            max_tokens=100
        )
        
        assert isinstance(response, Message)
        text = response.content[0].text
        # Should mention 100 or "hundred"
        assert "100" in text or "hundred" in text.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])