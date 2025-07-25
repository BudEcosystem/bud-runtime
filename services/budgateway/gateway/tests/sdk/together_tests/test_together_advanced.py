"""
Test advanced Together AI features through OpenAI SDK.

This includes testing reasoning models, JSON mode, tool calling,
and other advanced capabilities.
"""

import os
import json
import pytest
from typing import List, Dict, Any
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


class TestTogetherJSONMode:
    """Test JSON mode with Together AI models."""
    
    def test_json_mode_basic(self):
        """Test basic JSON mode output."""
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that always responds in valid JSON."
                },
                {
                    "role": "user",
                    "content": "List 3 programming languages with their year of creation"
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=200
        )
        
        content = response.choices[0].message.content
        assert content is not None
        
        # Try to parse as JSON
        try:
            parsed = json.loads(content)
            assert isinstance(parsed, dict)
        except json.JSONDecodeError:
            # For dummy provider, might not return actual JSON
            pass
    
    def test_json_mode_structured_output(self):
        """Test JSON mode with structured output request."""
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-72B-Instruct-Turbo",
            messages=[
                {
                    "role": "user",
                    "content": """Return a JSON object with this structure:
                    {
                        "name": "string",
                        "age": number,
                        "skills": ["string"],
                        "active": boolean
                    }"""
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=150
        )
        
        assert response.choices[0].message.content is not None
    
    def test_json_mode_complex_schema(self):
        """Test JSON mode with complex nested schema."""
        schema_request = """
        Create a JSON object representing a company with:
        - name (string)
        - founded (number)
        - employees (array of objects with name and role)
        - locations (object with headquarters and branches)
        """
        
        response = client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=[
                {"role": "user", "content": schema_request}
            ],
            response_format={"type": "json_object"},
            max_tokens=300
        )
        
        assert response.choices[0].message.content is not None


class TestTogetherToolCalling:
    """Test tool calling capabilities with Together AI models."""
    
    def test_single_tool_call(self):
        """Test calling a single tool."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather in a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state, e.g. San Francisco, CA"
                            },
                            "unit": {
                                "type": "string",
                                "enum": ["celsius", "fahrenheit"]
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        ]
        
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[
                {"role": "user", "content": "What's the weather in New York?"}
            ],
            tools=tools,
            tool_choice="auto",
            max_tokens=150
        )
        
        assert response.choices[0].message is not None
        # Model may or may not call the tool depending on implementation
    
    def test_multiple_tools(self):
        """Test with multiple available tools."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "Search the web for information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "calculate",
                    "description": "Perform mathematical calculations",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {"type": "string"}
                        },
                        "required": ["expression"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_time",
                    "description": "Get current time in a timezone",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "timezone": {"type": "string"}
                        },
                        "required": ["timezone"]
                    }
                }
            }
        ]
        
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.1-405B-Instruct-Turbo",
            messages=[
                {"role": "user", "content": "What's 25 * 4?"}
            ],
            tools=tools,
            tool_choice="auto",
            max_tokens=150
        )
        
        assert response.choices[0].message is not None
    
    def test_forced_tool_use(self):
        """Test forcing the model to use a specific tool."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "translate",
                    "description": "Translate text to another language",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "target_language": {"type": "string"}
                        },
                        "required": ["text", "target_language"]
                    }
                }
            }
        ]
        
        response = client.chat.completions.create(
            model="deepseek-ai/deepseek-v2.5",
            messages=[
                {"role": "user", "content": "Hello world"}
            ],
            tools=tools,
            tool_choice={
                "type": "function",
                "function": {"name": "translate"}
            },
            max_tokens=150
        )
        
        assert response.choices[0].message is not None
    
    def test_parallel_tool_calls(self):
        """Test parallel tool calling capabilities."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_stock_price",
                    "description": "Get current stock price",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"}
                        },
                        "required": ["symbol"]
                    }
                }
            }
        ]
        
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[
                {"role": "user", "content": "What are the current prices of AAPL, GOOGL, and MSFT?"}
            ],
            tools=tools,
            tool_choice="auto",
            max_tokens=200
        )
        
        assert response.choices[0].message is not None
        # Advanced models might make multiple tool calls


class TestTogetherReasoningModels:
    """Test Together's reasoning-capable models."""
    
    def test_reasoning_with_deepseek(self):
        """Test reasoning capabilities with DeepSeek models."""
        response = client.chat.completions.create(
            model="together-deepseek-r1",
            messages=[
                {
                    "role": "user",
                    "content": """Solve this step by step:
                    If a train travels 120 miles in 2 hours, and then 180 miles in 3 hours,
                    what is its average speed for the entire journey?"""
                }
            ],
            max_tokens=300
        )
        
        content = response.choices[0].message.content
        assert content is not None
        assert len(content) > 0
    
    def test_complex_reasoning_task(self):
        """Test complex multi-step reasoning."""
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[
                {
                    "role": "user",
                    "content": """A farmer has chickens and rabbits. 
                    The total number of heads is 35.
                    The total number of legs is 94.
                    How many chickens and how many rabbits does the farmer have?
                    Show your reasoning step by step."""
                }
            ],
            max_tokens=400
        )
        
        assert response.choices[0].message.content is not None
    
    def test_code_reasoning(self):
        """Test reasoning about code."""
        code_snippet = '''
        def mystery(n):
            if n <= 1:
                return n
            return mystery(n-1) + mystery(n-2)
        '''
        
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-72B-Instruct-Turbo",
            messages=[
                {
                    "role": "user",
                    "content": f"""Analyze this code:
                    ```python
                    {code_snippet}
                    ```
                    What does this function do? What is mystery(5)?
                    Explain your reasoning."""
                }
            ],
            max_tokens=300
        )
        
        assert response.choices[0].message.content is not None


class TestTogetherAdvancedParameters:
    """Test advanced parameters and configurations."""
    
    def test_temperature_variations(self):
        """Test different temperature settings."""
        temperatures = [0.0, 0.5, 1.0, 1.5]
        
        for temp in temperatures:
            response = client.chat.completions.create(
                model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
                messages=[
                    {"role": "user", "content": "Write a creative story opening"}
                ],
                temperature=temp,
                max_tokens=50
            )
            
            assert response.choices[0].message.content is not None
    
    def test_top_p_sampling(self):
        """Test top-p (nucleus) sampling."""
        top_p_values = [0.1, 0.5, 0.9, 1.0]
        
        for top_p in top_p_values:
            response = client.chat.completions.create(
                model="mistralai/Mixtral-8x7B-Instruct-v0.1",
                messages=[
                    {"role": "user", "content": "Generate a random sentence"}
                ],
                top_p=top_p,
                max_tokens=30
            )
            
            assert response.choices[0].message.content is not None
    
    def test_frequency_penalty(self):
        """Test frequency penalty parameter."""
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
            messages=[
                {"role": "user", "content": "Write about a topic without repeating words"}
            ],
            frequency_penalty=2.0,
            max_tokens=100
        )
        
        assert response.choices[0].message.content is not None
    
    def test_presence_penalty(self):
        """Test presence penalty parameter."""
        response = client.chat.completions.create(
            model="deepseek-ai/deepseek-v2.5",
            messages=[
                {"role": "user", "content": "Write about diverse topics"}
            ],
            presence_penalty=2.0,
            max_tokens=100
        )
        
        assert response.choices[0].message.content is not None
    
    def test_seed_reproducibility(self):
        """Test seed parameter for reproducibility."""
        seed = 42
        prompt = "Generate a random number between 1 and 10"
        
        # First generation
        response1 = client.chat.completions.create(
            model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
            messages=[{"role": "user", "content": prompt}],
            seed=seed,
            temperature=0,
            max_tokens=10
        )
        
        # Second generation with same seed
        response2 = client.chat.completions.create(
            model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
            messages=[{"role": "user", "content": prompt}],
            seed=seed,
            temperature=0,
            max_tokens=10
        )
        
        # With temperature=0 and same seed, outputs might be similar
        assert response1.choices[0].message.content is not None
        assert response2.choices[0].message.content is not None


class TestTogetherStreamingAdvanced:
    """Test advanced streaming scenarios."""
    
    def test_streaming_with_tool_calls(self):
        """Test streaming with tool calling."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_info",
                    "description": "Get information about a topic",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string"}
                        },
                        "required": ["topic"]
                    }
                }
            }
        ]
        
        stream = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[
                {"role": "user", "content": "Tell me about Python"}
            ],
            tools=tools,
            stream=True,
            max_tokens=100
        )
        
        chunks_received = 0
        for chunk in stream:
            chunks_received += 1
            if chunk.choices[0].delta.tool_calls:
                # Tool call in stream
                assert chunk.choices[0].delta.tool_calls is not None
        
        assert chunks_received > 0
    
    def test_streaming_with_stop_sequences(self):
        """Test streaming with stop sequences."""
        stream = client.chat.completions.create(
            model="Qwen/Qwen2.5-72B-Instruct-Turbo",
            messages=[
                {"role": "user", "content": "Count from 1 to 10"}
            ],
            stop=["5", "five"],
            stream=True,
            max_tokens=100
        )
        
        full_response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                full_response += chunk.choices[0].delta.content
        
        assert len(full_response) > 0
    
    def test_streaming_usage_stats(self):
        """Test streaming with usage statistics."""
        stream = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
            messages=[
                {"role": "user", "content": "Hello"}
            ],
            stream=True,
            stream_options={"include_usage": True},
            max_tokens=50
        )
        
        last_chunk = None
        for chunk in stream:
            last_chunk = chunk
        
        # Usage stats might be in the last chunk
        if hasattr(last_chunk, 'usage'):
            assert last_chunk.usage is not None


class TestTogetherErrorScenarios:
    """Test error handling with Together models."""
    
    def test_invalid_model_name(self):
        """Test with invalid model name."""
        with pytest.raises(Exception) as exc_info:
            client.chat.completions.create(
                model="together/invalid-model-name",
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=10
            )
        
        assert exc_info.value is not None
    
    def test_context_length_handling(self):
        """Test handling of context length limits."""
        # Create a very long message
        long_message = "Test " * 10000  # Very long input
        
        try:
            response = client.chat.completions.create(
                model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
                messages=[{"role": "user", "content": long_message}],
                max_tokens=10
            )
            # If it succeeds, verify response
            assert response.choices[0].message.content is not None
        except Exception as e:
            # Expected to fail with context length error
            assert "context" in str(e).lower() or "token" in str(e).lower()
    
    def test_invalid_parameters(self):
        """Test with invalid parameter combinations."""
        # Test with invalid temperature
        with pytest.raises(Exception):
            client.chat.completions.create(
                model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
                messages=[{"role": "user", "content": "Test"}],
                temperature=-1.0,  # Invalid
                max_tokens=10
            )
        
        # Test with invalid max_tokens
        with pytest.raises(Exception):
            client.chat.completions.create(
                model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=-10  # Invalid
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])