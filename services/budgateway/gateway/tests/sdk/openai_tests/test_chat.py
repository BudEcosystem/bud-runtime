import os
import pytest
from openai import OpenAI
from dotenv import load_dotenv
import json

load_dotenv()

# Configuration
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3000")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Clients
tensorzero_client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)

openai_client = OpenAI(
    api_key=OPENAI_API_KEY
)


class TestChatCompletions:
    """Test chat completions endpoint compatibility"""

    def test_basic_chat_completion(self):
        """Test basic chat completion request"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'Hello, World!' and nothing else."}
        ]
        
        # TensorZero request
        tz_response = tensorzero_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0,
            max_tokens=20
        )
        
        # Verify response structure
        assert tz_response.id
        assert tz_response.object == "chat.completion"
        assert tz_response.model == "gpt-3.5-turbo"
        assert len(tz_response.choices) == 1
        assert tz_response.choices[0].message.role == "assistant"
        assert tz_response.choices[0].message.content
        assert tz_response.usage.prompt_tokens > 0
        assert tz_response.usage.completion_tokens > 0
        assert tz_response.usage.total_tokens > 0

    def test_multiple_messages(self):
        """Test conversation with multiple messages"""
        messages = [
            {"role": "system", "content": "You are a math tutor."},
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "2+2 equals 4."},
            {"role": "user", "content": "What about 3+3?"}
        ]
        
        response = tensorzero_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0
        )
        
        assert response.choices[0].message.content
        assert response.choices[0].finish_reason in ["stop", "length"]

    def test_streaming_chat_completion(self):
        """Test streaming chat completion"""
        messages = [{"role": "user", "content": "Count from 1 to 5"}]
        
        stream = tensorzero_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            stream=True,
            temperature=0
        )
        
        chunks = []
        for chunk in stream:
            chunks.append(chunk)
            assert chunk.object == "chat.completion.chunk"
            assert chunk.model == "gpt-3.5-turbo"
            if chunk.choices:
                assert chunk.choices[0].delta
        
        assert len(chunks) > 1  # Should have multiple chunks

    def test_function_calling(self):
        """Test function calling capability"""
        messages = [{"role": "user", "content": "What's the weather in San Francisco?"}]
        
        tools = [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather in a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state"
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"]
                        }
                    },
                    "required": ["location"]
                }
            }
        }]
        
        response = tensorzero_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        # Check if model decided to use a function
        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            assert tool_call.function.name == "get_weather"
            args = json.loads(tool_call.function.arguments)
            assert "location" in args
            assert "San Francisco" in args["location"]

    def test_different_models(self):
        """Test with different model variants"""
        messages = [{"role": "user", "content": "Say 'test'"}]
        
        models = ["gpt-3.5-turbo", "gpt-4"]
        
        for model in models:
            response = tensorzero_client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=10
            )
            assert response.model == model
            assert response.choices[0].message.content

    def test_error_handling(self):
        """Test error handling for invalid requests"""
        # Invalid model
        with pytest.raises(Exception) as exc_info:
            tensorzero_client.chat.completions.create(
                model="invalid-model",
                messages=[{"role": "user", "content": "test"}]
            )
        
        # Empty messages
        with pytest.raises(Exception) as exc_info:
            tensorzero_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[]
            )
        
        # Invalid message format
        with pytest.raises(Exception) as exc_info:
            tensorzero_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"content": "test"}]  # Missing role
            )

    def test_completion_parameters(self):
        """Test various completion parameters"""
        messages = [{"role": "user", "content": "Write a haiku about Python"}]
        
        response = tensorzero_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=50,
            top_p=0.9,
            frequency_penalty=0.5,
            presence_penalty=0.5,
            # Removing untill tensorzero supports n parameter
            # n=2,  # Request 2 completions
            stop=["\n\n"]
        )
        
        # assert len(response.choices) == 2
        for choice in response.choices:
            assert choice.message.content
            assert choice.index in [0, 1]

    @pytest.mark.asyncio
    async def test_async_chat_completion(self):
        """Test async chat completion"""
        from openai import AsyncOpenAI
        
        async_client = AsyncOpenAI(
            base_url=f"{TENSORZERO_BASE_URL}/v1",
            api_key=TENSORZERO_API_KEY
        )
        
        messages = [{"role": "user", "content": "Say 'async test'"}]
        
        response = await async_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=10
        )
        
        assert response.choices[0].message.content
        assert "async" in response.choices[0].message.content.lower() or "test" in response.choices[0].message.content.lower()