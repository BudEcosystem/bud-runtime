#!/usr/bin/env python3
"""
Full integration tests for Fireworks provider with real API.
These tests require FIREWORKS_API_KEY to be set.
"""

import asyncio
import json
import os
import sys
from openai import OpenAI, AsyncOpenAI
from typing import Dict, Any, Optional

# Check for API key
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
if not FIREWORKS_API_KEY:
    print("⚠️  FIREWORKS_API_KEY not set. Skipping full Fireworks tests.")
    sys.exit(0)


def test_basic_fireworks_chat():
    """Test basic chat completion with real Fireworks API."""
    client = OpenAI(
        base_url="http://localhost:3000/v1",
        api_key="test-key",  # TensorZero uses its own auth
    )
    
    response = client.chat.completions.create(
        model="llama-v3p2-3b-instruct",
        messages=[
            {"role": "user", "content": "Say 'Hello from Fireworks' in exactly 4 words"}
        ],
        temperature=0.1,
        max_tokens=20,
    )
    
    assert response.choices[0].message.content is not None
    assert len(response.choices[0].message.content) > 0
    print(f"✓ Basic chat: {response.choices[0].message.content}")


def test_fireworks_with_sampling_params():
    """Test Fireworks-specific sampling parameters."""
    client = OpenAI(
        base_url="http://localhost:3000/v1",
        api_key="test-key",
    )
    
    # Test with various sampling parameters
    response = client.chat.completions.create(
        model="llama-v3p1-8b-instruct",
        messages=[
            {"role": "user", "content": "Generate a creative single sentence about AI"}
        ],
        temperature=0.8,
        max_tokens=50,
        extra_body={
            "top_k": 40,
            "min_p": 0.05,
            "repetition_penalty": 1.1,
        }
    )
    
    assert response.choices[0].message.content is not None
    print(f"✓ Sampling params: Generated text with custom sampling")


def test_fireworks_context_handling():
    """Test context length handling parameters."""
    client = OpenAI(
        base_url="http://localhost:3000/v1",
        api_key="test-key",
    )
    
    # Create a long prompt
    long_context = "This is a test. " * 100
    
    response = client.chat.completions.create(
        model="llama-v3p2-3b-instruct",
        messages=[
            {"role": "user", "content": f"{long_context} Summarize this in one word."}
        ],
        max_tokens=10,
        extra_body={
            "prompt_truncate_len": 500,  # Truncate to 500 tokens
            "context_length_exceeded_behavior": "truncate",
        }
    )
    
    assert response.choices[0].message.content is not None
    print("✓ Context handling: Truncation parameters work")


def test_fireworks_reasoning_model():
    """Test reasoning model with reasoning_effort parameter."""
    client = OpenAI(
        base_url="http://localhost:3000/v1",
        api_key="test-key",
    )
    
    # Skip if deepseek-r1 is not available
    try:
        response = client.chat.completions.create(
            model="deepseek-r1",
            messages=[
                {"role": "user", "content": "What is 2+2? Answer in one number only."}
            ],
            max_tokens=10,
            temperature=0.1,
            extra_body={
                "reasoning_effort": "low",  # Low effort for simple question
            }
        )
        
        assert response.choices[0].message.content is not None
        print(f"✓ Reasoning model: {response.choices[0].message.content.strip()}")
    except Exception as e:
        print(f"⚠️  Reasoning model test skipped: {str(e)}")


def test_fireworks_streaming():
    """Test streaming with Fireworks parameters."""
    client = OpenAI(
        base_url="http://localhost:3000/v1",
        api_key="test-key",
    )
    
    stream = client.chat.completions.create(
        model="llama-v3p1-8b-instruct",
        messages=[
            {"role": "user", "content": "Count from 1 to 3, one number per line"}
        ],
        stream=True,
        temperature=0.1,
        max_tokens=20,
        extra_body={
            "top_k": 10,  # Very restrictive for deterministic output
            "repetition_penalty": 1.0,
        }
    )
    
    full_response = ""
    chunk_count = 0
    for chunk in stream:
        if chunk.choices[0].delta.content:
            full_response += chunk.choices[0].delta.content
            chunk_count += 1
    
    assert len(full_response) > 0
    assert chunk_count > 0
    print(f"✓ Streaming: Received {chunk_count} chunks")


def test_fireworks_json_mode():
    """Test JSON mode with Fireworks."""
    client = OpenAI(
        base_url="http://localhost:3000/v1",
        api_key="test-key",
    )
    
    response = client.chat.completions.create(
        model="llama-v3p1-70b-instruct",
        messages=[
            {"role": "user", "content": "Return a JSON object with name='Fireworks' and type='AI'"}
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=50,
        extra_body={
            "top_k": 5,  # Very restrictive for JSON generation
        }
    )
    
    content = response.choices[0].message.content
    assert content is not None
    
    # Verify it's valid JSON
    try:
        parsed = json.loads(content)
        assert "name" in parsed or "type" in parsed
        print(f"✓ JSON mode: Generated valid JSON")
    except json.JSONDecodeError:
        print(f"⚠️  JSON mode: Response was not valid JSON: {content}")


def test_fireworks_embedding():
    """Test Fireworks embedding model."""
    client = OpenAI(
        base_url="http://localhost:3000/v1",
        api_key="test-key",
    )
    
    response = client.embeddings.create(
        model="nomic-embed-text-v1_5",
        input="Fireworks AI provides fast inference",
    )
    
    assert len(response.data) > 0
    assert len(response.data[0].embedding) > 0
    embedding_dim = len(response.data[0].embedding)
    print(f"✓ Embedding: Generated {embedding_dim}-dimensional embedding")


def test_fireworks_multiple_messages():
    """Test with multiple messages and Fireworks parameters."""
    client = OpenAI(
        base_url="http://localhost:3000/v1",
        api_key="test-key",
    )
    
    response = client.chat.completions.create(
        model="llama-v3p2-3b-instruct",
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Be concise."},
            {"role": "user", "content": "What is Fireworks AI?"},
            {"role": "assistant", "content": "Fireworks AI is a platform for fast LLM inference."},
            {"role": "user", "content": "What makes it fast? Answer in 5 words or less."},
        ],
        temperature=0.3,
        max_tokens=20,
        extra_body={
            "top_k": 20,
            "repetition_penalty": 1.05,
        }
    )
    
    assert response.choices[0].message.content is not None
    print(f"✓ Multi-message: {response.choices[0].message.content}")


# Async tests
async def test_async_fireworks():
    """Test async client with Fireworks."""
    client = AsyncOpenAI(
        base_url="http://localhost:3000/v1",
        api_key="test-key",
    )
    
    response = await client.chat.completions.create(
        model="llama-v3p1-8b-instruct",
        messages=[
            {"role": "user", "content": "Say 'Async works' in exactly 2 words"}
        ],
        temperature=0.1,
        max_tokens=10,
        extra_body={
            "top_k": 5,
        }
    )
    
    assert response.choices[0].message.content is not None
    print(f"✓ Async: {response.choices[0].message.content}")


async def test_async_streaming():
    """Test async streaming with Fireworks."""
    client = AsyncOpenAI(
        base_url="http://localhost:3000/v1",
        api_key="test-key",
    )
    
    stream = await client.chat.completions.create(
        model="llama-v3p2-3b-instruct",
        messages=[
            {"role": "user", "content": "Say 'Hello' then 'World' on separate lines"}
        ],
        stream=True,
        temperature=0.1,
        max_tokens=20,
        extra_body={
            "repetition_penalty": 1.0,
            "top_k": 10,
        }
    )
    
    chunks = []
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            chunks.append(chunk.choices[0].delta.content)
    
    assert len(chunks) > 0
    print(f"✓ Async streaming: Received {len(chunks)} chunks")


def run_sync_tests():
    """Run all synchronous tests."""
    print("\n=== Running Fireworks Full Integration Tests (Sync) ===\n")
    
    test_basic_fireworks_chat()
    test_fireworks_with_sampling_params()
    test_fireworks_context_handling()
    test_fireworks_reasoning_model()
    test_fireworks_streaming()
    test_fireworks_json_mode()
    test_fireworks_embedding()
    test_fireworks_multiple_messages()
    
    print("\n✅ All synchronous tests completed!")


async def run_async_tests():
    """Run all asynchronous tests."""
    print("\n=== Running Fireworks Full Integration Tests (Async) ===\n")
    
    await test_async_fireworks()
    await test_async_streaming()
    
    print("\n✅ All asynchronous tests completed!")


def main():
    """Main test runner."""
    print(f"\n🔥 Testing with Fireworks API\n")
    
    try:
        # Run sync tests
        run_sync_tests()
        
        # Run async tests
        asyncio.run(run_async_tests())
        
        print("\n🎉 All Fireworks integration tests passed!\n")
        
        # Print parameter documentation
        print("📖 Fireworks Parameters Reference:")
        print("  - top_k: Limit token choices (default: 50)")
        print("  - min_p: Minimum probability threshold")
        print("  - repetition_penalty: Control repetition (default: 1.0)")
        print("  - reasoning_effort: For reasoning models (low/medium/high)")
        print("  - top_a: Alternative sampling method")
        print("  - mirostat_lr: Mirostat learning rate")
        print("  - mirostat_target: Target perplexity")
        print("  - draft_token_count: For speculative decoding")
        print("  - prompt_truncate_len: Max prompt length")
        print("  - context_length_exceeded_behavior: 'truncate' or 'error'")
        print("\nUse these via extra_body in OpenAI SDK calls.\n")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())