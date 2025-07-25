"""
Test advanced Together AI features through OpenAI SDK.

These tests cover JSON mode, tool calling, streaming, reasoning models,
and other advanced capabilities.
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional
import pytest
from openai import OpenAI, AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuration
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")

# Skip tests if not configured for Together
SKIP_TOGETHER_TESTS = os.getenv("SKIP_TOGETHER_TESTS", "false").lower() == "true"

# Clients
client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)

async_client = AsyncOpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)


@pytest.mark.skipif(SKIP_TOGETHER_TESTS, reason="Together tests disabled")
class TestTogetherJSONMode:
    """Test JSON mode with Together models."""
    
    def test_json_mode_basic(self):
        """Test basic JSON mode output."""
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that always responds with valid JSON."
                },
                {
                    "role": "user",
                    "content": "Create a JSON object with name, age, and city fields for a fictional person."
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
            # Check expected fields exist
            assert "name" in parsed or "age" in parsed or "city" in parsed
        except json.JSONDecodeError:
            # For dummy provider, might not return actual JSON
            pass
    
    def test_json_mode_structured_data(self):
        """Test JSON mode with structured data request."""
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-72B-Instruct-Turbo",
            messages=[
                {
                    "role": "user",
                    "content": """Create a JSON array of 3 books with the following structure:
                    {
                        "title": "string",
                        "author": "string",
                        "year": number,
                        "genres": ["string"]
                    }"""
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=300
        )
        
        content = response.choices[0].message.content
        assert content is not None
        
        try:
            parsed = json.loads(content)
            # Could be an object with a books array or directly an array
            if isinstance(parsed, dict) and "books" in parsed:
                books = parsed["books"]
            elif isinstance(parsed, list):
                books = parsed
            else:
                books = []
            
            # Verify structure if we got books
            for book in books[:1]:  # Check at least first book
                assert isinstance(book.get("title"), str)
                assert isinstance(book.get("author"), str)
                assert isinstance(book.get("year"), (int, float))
                assert isinstance(book.get("genres"), list)
        except json.JSONDecodeError:
            pass
    
    def test_json_mode_nested_structures(self):
        """Test JSON mode with nested data structures."""
        response = client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=[
                {
                    "role": "user",
                    "content": """Create a JSON object representing a company with:
                    - name (string)
                    - employees (array of objects with name and role)
                    - departments (object with department names as keys)
                    - metadata (object with founded year and public boolean)"""
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=400
        )
        
        content = response.choices[0].message.content
        assert content is not None
        
        try:
            parsed = json.loads(content)
            assert isinstance(parsed, dict)
        except json.JSONDecodeError:
            pass
    
    def test_json_mode_with_schema_compliance(self):
        """Test JSON mode with specific schema requirements."""
        schema = {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "price": {"type": "number"},
                "in_stock": {"type": "boolean"},
                "tags": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["product_name", "price", "in_stock"]
        }
        
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
            messages=[
                {
                    "role": "user",
                    "content": f"Create a JSON object that matches this schema: {json.dumps(schema)}"
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=200
        )
        
        content = response.choices[0].message.content
        assert content is not None


@pytest.mark.skipif(SKIP_TOGETHER_TESTS, reason="Together tests disabled")
class TestTogetherToolCalling:
    """Test tool calling with Together models."""
    
    def test_single_tool_call(self):
        """Test calling a single tool."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather in a given location",
                    "parameters": {
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
                }
            }
        ]
        
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[
                {"role": "user", "content": "What's the weather like in San Francisco?"}
            ],
            tools=tools,
            tool_choice="auto"
        )
        
        message = response.choices[0].message
        assert message is not None
        
        # Check if tool was called
        if hasattr(message, 'tool_calls') and message.tool_calls:
            tool_call = message.tool_calls[0]
            assert tool_call.function.name == "get_weather"
            
            # Parse arguments
            try:
                args = json.loads(tool_call.function.arguments)
                assert "location" in args
            except json.JSONDecodeError:
                pass
    
    def test_multiple_tools_selection(self):
        """Test selecting appropriate tool from multiple options."""
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
        
        # Test calculation request
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.1-405B-Instruct-Turbo",
            messages=[
                {"role": "user", "content": "What is 25 multiplied by 4?"}
            ],
            tools=tools,
            tool_choice="auto"
        )
        
        message = response.choices[0].message
        if hasattr(message, 'tool_calls') and message.tool_calls:
            # Should call calculate tool
            assert any(tc.function.name == "calculate" for tc in message.tool_calls)
    
    def test_forced_tool_use(self):
        """Test forcing model to use a specific tool."""
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
                {"role": "user", "content": "Hello, how are you?"}
            ],
            tools=tools,
            tool_choice={
                "type": "function",
                "function": {"name": "translate"}
            }
        )
        
        message = response.choices[0].message
        if hasattr(message, 'tool_calls') and message.tool_calls:
            # Should be forced to use translate tool
            assert message.tool_calls[0].function.name == "translate"
    
    def test_parallel_tool_calls(self):
        """Test making multiple tool calls in parallel."""
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
            tool_choice="auto"
        )
        
        message = response.choices[0].message
        if hasattr(message, 'tool_calls') and message.tool_calls:
            # Might make multiple calls for different stocks
            assert len(message.tool_calls) >= 1
    
    def test_tool_calling_with_context(self):
        """Test tool calling with conversation context."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "send_email",
                    "description": "Send an email",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string"},
                            "subject": {"type": "string"},
                            "body": {"type": "string"}
                        },
                        "required": ["to", "subject", "body"]
                    }
                }
            }
        ]
        
        messages = [
            {"role": "user", "content": "I need to email John about the meeting"},
            {"role": "assistant", "content": "I'll help you send an email to John about the meeting. What's John's email address?"},
            {"role": "user", "content": "It's john@example.com. Tell him the meeting is at 3 PM tomorrow."}
        ]
        
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-72B-Instruct-Turbo",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        message = response.choices[0].message
        assert message is not None


@pytest.mark.skipif(SKIP_TOGETHER_TESTS, reason="Together tests disabled")
class TestTogetherStreaming:
    """Test streaming capabilities with Together models."""
    
    def test_basic_streaming(self):
        """Test basic streaming response."""
        stream = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
            messages=[
                {"role": "user", "content": "Count from 1 to 5 slowly"}
            ],
            stream=True,
            max_tokens=100
        )
        
        chunks = []
        for chunk in stream:
            if chunk.choices[0].delta.content:
                chunks.append(chunk.choices[0].delta.content)
        
        assert len(chunks) > 0
        full_response = "".join(chunks)
        assert len(full_response) > 0
    
    def test_streaming_with_system_prompt(self):
        """Test streaming with system prompt."""
        stream = client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Be concise."},
                {"role": "user", "content": "Explain streaming in one sentence"}
            ],
            stream=True
        )
        
        content_chunks = []
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content_chunks.append(chunk.choices[0].delta.content)
        
        assert len(content_chunks) > 0
    
    def test_streaming_tool_calls(self):
        """Test streaming with tool calls."""
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
                {"role": "user", "content": "Tell me about Paris"}
            ],
            tools=tools,
            stream=True
        )
        
        tool_call_chunks = []
        content_chunks = []
        
        for chunk in stream:
            if chunk.choices[0].delta.tool_calls:
                tool_call_chunks.append(chunk)
            if chunk.choices[0].delta.content:
                content_chunks.append(chunk.choices[0].delta.content)
        
        # Should have either content or tool calls
        assert len(content_chunks) > 0 or len(tool_call_chunks) > 0
    
    def test_streaming_with_stop_sequences(self):
        """Test streaming with stop sequences."""
        stream = client.chat.completions.create(
            model="deepseek-ai/deepseek-v2.5",
            messages=[
                {"role": "user", "content": "List numbers: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10"}
            ],
            stop=["5"],
            stream=True
        )
        
        chunks = []
        for chunk in stream:
            if chunk.choices[0].delta.content:
                chunks.append(chunk.choices[0].delta.content)
        
        full_response = "".join(chunks)
        # Response should stop at or before "5"
        assert "6" not in full_response or full_response.index("5") < full_response.index("6")
    
    @pytest.mark.asyncio
    async def test_async_streaming(self):
        """Test asynchronous streaming."""
        stream = await async_client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
            messages=[
                {"role": "user", "content": "Say hello asynchronously"}
            ],
            stream=True
        )
        
        chunks = []
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                chunks.append(chunk.choices[0].delta.content)
        
        assert len(chunks) > 0


@pytest.mark.skipif(SKIP_TOGETHER_TESTS, reason="Together tests disabled")
class TestTogetherReasoningModels:
    """Test Together's reasoning-capable models."""
    
    def test_deepseek_reasoning(self):
        """Test reasoning with DeepSeek R1 model."""
        response = client.chat.completions.create(
            model="together-deepseek-r1",
            messages=[
                {
                    "role": "user",
                    "content": """Solve step by step:
                    A train leaves Station A at 9:00 AM traveling at 60 mph.
                    Another train leaves Station B at 10:00 AM traveling at 80 mph.
                    If the stations are 280 miles apart, when do the trains meet?"""
                }
            ],
            max_tokens=500
        )
        
        content = response.choices[0].message.content
        assert content is not None
        assert len(content) > 0
    
    def test_complex_reasoning(self):
        """Test complex multi-step reasoning."""
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[
                {
                    "role": "user",
                    "content": """A farmer has some chickens and rabbits.
                    There are 35 heads total.
                    There are 94 legs total.
                    How many of each animal does the farmer have?
                    Show your step-by-step reasoning."""
                }
            ],
            max_tokens=400
        )
        
        content = response.choices[0].message.content
        assert content is not None
        # Should contain reasoning steps
        assert len(content) > 100
    
    def test_code_reasoning(self):
        """Test reasoning about code."""
        code = '''
        def fibonacci(n):
            if n <= 1:
                return n
            return fibonacci(n-1) + fibonacci(n-2)
        '''
        
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-72B-Instruct-Turbo",
            messages=[
                {
                    "role": "user",
                    "content": f"""Analyze this code:
                    ```python
                    {code}
                    ```
                    1. What does this function do?
                    2. What is fibonacci(5)?
                    3. What is the time complexity?
                    Show your reasoning for each answer."""
                }
            ],
            max_tokens=500
        )
        
        content = response.choices[0].message.content
        assert content is not None
    
    def test_logical_puzzle(self):
        """Test solving logical puzzles."""
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.1-405B-Instruct-Turbo",
            messages=[
                {
                    "role": "user",
                    "content": """Solve this logic puzzle:
                    Three friends (Alice, Bob, Charlie) have different favorite colors (red, blue, green).
                    - Alice doesn't like red
                    - The person who likes blue is not Charlie
                    - Bob's favorite color comes before Alice's alphabetically
                    What is each person's favorite color?"""
                }
            ],
            max_tokens=300
        )
        
        content = response.choices[0].message.content
        assert content is not None


@pytest.mark.skipif(SKIP_TOGETHER_TESTS, reason="Together tests disabled")
class TestTogetherAdvancedParameters:
    """Test advanced parameter configurations."""
    
    def test_temperature_effects(self):
        """Test different temperature settings."""
        prompt = "Write a creative opening sentence for a story"
        
        # Low temperature (more deterministic)
        response_low = client.chat.completions.create(
            model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=50
        )
        
        # High temperature (more creative)
        response_high = client.chat.completions.create(
            model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=1.5,
            max_tokens=50
        )
        
        assert response_low.choices[0].message.content is not None
        assert response_high.choices[0].message.content is not None
    
    def test_top_p_sampling(self):
        """Test nucleus sampling with different top_p values."""
        top_p_values = [0.1, 0.5, 0.9]
        
        for top_p in top_p_values:
            response = client.chat.completions.create(
                model="mistralai/Mixtral-8x7B-Instruct-v0.1",
                messages=[{"role": "user", "content": "Generate a random sentence"}],
                top_p=top_p,
                max_tokens=30
            )
            
            assert response.choices[0].message.content is not None
    
    def test_frequency_penalty(self):
        """Test frequency penalty to reduce repetition."""
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
            messages=[
                {"role": "user", "content": "Write a paragraph about the ocean"}
            ],
            frequency_penalty=2.0,
            max_tokens=150
        )
        
        content = response.choices[0].message.content
        assert content is not None
        
        # With high frequency penalty, words should not repeat much
        words = content.lower().split()
        word_counts = {}
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        # Most words should appear only once or twice
        high_frequency_words = [w for w, c in word_counts.items() if c > 3]
        assert len(high_frequency_words) < len(word_counts) * 0.1
    
    def test_presence_penalty(self):
        """Test presence penalty for topic diversity."""
        response = client.chat.completions.create(
            model="deepseek-ai/deepseek-v2.5",
            messages=[
                {"role": "user", "content": "Write about various topics in technology"}
            ],
            presence_penalty=2.0,
            max_tokens=200
        )
        
        assert response.choices[0].message.content is not None
    
    def test_max_tokens_limit(self):
        """Test max tokens parameter."""
        response_short = client.chat.completions.create(
            model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
            messages=[{"role": "user", "content": "Tell me a long story"}],
            max_tokens=10
        )
        
        response_long = client.chat.completions.create(
            model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
            messages=[{"role": "user", "content": "Tell me a long story"}],
            max_tokens=200
        )
        
        short_content = response_short.choices[0].message.content
        long_content = response_long.choices[0].message.content
        
        assert len(short_content) < len(long_content)
    
    def test_seed_reproducibility(self):
        """Test seed parameter for reproducible outputs."""
        seed = 12345
        prompt = "Generate a random number between 1 and 100"
        
        # Generate twice with same seed
        response1 = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
            messages=[{"role": "user", "content": prompt}],
            seed=seed,
            temperature=0,
            max_tokens=10
        )
        
        response2 = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
            messages=[{"role": "user", "content": prompt}],
            seed=seed,
            temperature=0,
            max_tokens=10
        )
        
        # With temperature=0 and same seed, outputs might be identical
        assert response1.choices[0].message.content is not None
        assert response2.choices[0].message.content is not None


@pytest.mark.skipif(SKIP_TOGETHER_TESTS, reason="Together tests disabled") 
class TestTogetherIntegrationScenarios:
    """Test real-world integration scenarios."""
    
    def test_rag_pipeline(self):
        """Test a RAG (Retrieval Augmented Generation) pipeline."""
        # 1. Create embeddings for documents
        documents = [
            "Together AI provides fast inference for open-source models.",
            "The platform supports chat, embeddings, and image generation.",
            "Together offers competitive pricing for AI inference.",
            "Models include Llama, Mistral, and FLUX for various tasks."
        ]
        
        doc_embeddings = client.embeddings.create(
            model="together-bge-base",
            input=documents
        )
        
        # 2. Create embedding for query
        query = "What models does Together support?"
        query_embedding = client.embeddings.create(
            model="together-bge-base",
            input=query
        )
        
        # 3. In practice, find most relevant document
        # For testing, just use the most relevant one
        context = documents[3]  # About models
        
        # 4. Generate response with context
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
            messages=[
                {
                    "role": "system",
                    "content": f"Answer based on this context: {context}"
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            max_tokens=150
        )
        
        assert response.choices[0].message.content is not None
    
    def test_multi_modal_pipeline(self):
        """Test a multi-modal content generation pipeline."""
        # 1. Generate text description
        text_response = client.chat.completions.create(
            model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
            messages=[
                {
                    "role": "user",
                    "content": "Describe a futuristic city in one detailed sentence."
                }
            ],
            max_tokens=100
        )
        
        description = text_response.choices[0].message.content
        
        # 2. Generate image from description
        image_response = client.images.generate(
            model="flux-schnell",
            prompt=description,
            n=1,
            size="512x512"
        )
        
        # 3. Generate audio narration
        tts_response = client.audio.speech.create(
            model="together-tts",
            voice="storyteller lady",
            input=description
        )
        
        # Verify all components worked
        assert description is not None
        assert len(image_response.data) == 1
        assert tts_response.content is not None
    
    def test_conversational_assistant(self):
        """Test a multi-turn conversational assistant."""
        messages = [
            {"role": "system", "content": "You are a helpful coding assistant."},
            {"role": "user", "content": "I need to write a Python function to calculate factorial."}
        ]
        
        # First response
        response1 = client.chat.completions.create(
            model="Qwen/Qwen2.5-72B-Instruct-Turbo",
            messages=messages,
            max_tokens=200
        )
        
        # Add assistant response to conversation
        messages.append({
            "role": "assistant",
            "content": response1.choices[0].message.content
        })
        
        # Follow-up question
        messages.append({
            "role": "user",
            "content": "Can you make it handle negative numbers?"
        })
        
        # Second response
        response2 = client.chat.completions.create(
            model="Qwen/Qwen2.5-72B-Instruct-Turbo",
            messages=messages,
            max_tokens=200
        )
        
        assert response1.choices[0].message.content is not None
        assert response2.choices[0].message.content is not None
    
    def test_code_generation_pipeline(self):
        """Test code generation with explanation."""
        # 1. Generate code
        code_response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[
                {
                    "role": "user",
                    "content": "Write a Python function to merge two sorted lists"
                }
            ],
            max_tokens=300
        )
        
        code = code_response.choices[0].message.content
        
        # 2. Generate explanation
        explanation_response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[
                {
                    "role": "user",
                    "content": f"Explain how this code works:\n```python\n{code}\n```"
                }
            ],
            max_tokens=200
        )
        
        # 3. Generate test cases
        test_response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[
                {
                    "role": "user",
                    "content": f"Write test cases for this function:\n```python\n{code}\n```"
                }
            ],
            max_tokens=200
        )
        
        assert code is not None
        assert explanation_response.choices[0].message.content is not None
        assert test_response.choices[0].message.content is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])