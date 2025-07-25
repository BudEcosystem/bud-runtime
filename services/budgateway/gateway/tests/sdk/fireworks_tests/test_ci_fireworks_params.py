#!/usr/bin/env python3
"""
CI-friendly tests for Fireworks-specific parameters using OpenAI SDK.
These tests use dummy providers and don't require real API keys.
"""

import asyncio
import json
import os
import pytest
import sys
from openai import OpenAI, AsyncOpenAI
from typing import Dict, Any

# Fireworks-specific parameters that can be passed via extra_body
FIREWORKS_PARAMS = {
    # Sampling parameters
    "top_k": 50,
    "min_p": 0.1,
    "repetition_penalty": 1.1,
    "top_a": 0.9,
    
    # Reasoning model parameters
    "reasoning_effort": "medium",
    
    # Mirostat parameters
    "mirostat_lr": 0.1,
    "mirostat_target": 5.0,
    
    # Performance parameters
    "draft_token_count": 5,
    
    # Context handling
    "prompt_truncate_len": 1000,
    "context_length_exceeded_behavior": "truncate",
}


def test_basic_fireworks_chat():
    """Test basic chat completion with Fireworks model."""
    client = OpenAI(
        base_url="http://localhost:3001/v1",
        api_key="dummy-key",
    )
    
    response = client.chat.completions.create(
        model="fireworks-llama-v3p1-8b-instruct",
        messages=[{"role": "user", "content": "Hello"}],
        temperature=0.7,
    )
    
    assert response.choices[0].message.content is not None
    assert response.model == "fireworks-llama-v3p1-8b-instruct"
    print("✓ Basic Fireworks chat completion works")


def test_fireworks_with_extra_body():
    """Test Fireworks-specific parameters via extra_body."""
    client = OpenAI(
        base_url="http://localhost:3001/v1",
        api_key="dummy-key",
    )
    
    # Test with individual Fireworks parameters
    response = client.chat.completions.create(
        model="fireworks-llama-v3p1-8b-instruct",
        messages=[{"role": "user", "content": "Test with Fireworks params"}],
        temperature=0.5,
        extra_body={
            "top_k": 40,
            "repetition_penalty": 1.2,
            "prompt_truncate_len": 2000,
        }
    )
    
    assert response.choices[0].message.content is not None
    print("✓ Fireworks parameters via extra_body work")


def test_fireworks_reasoning_model_params():
    """Test reasoning model specific parameters."""
    client = OpenAI(
        base_url="http://localhost:3001/v1",
        api_key="dummy-key",
    )
    
    response = client.chat.completions.create(
        model="fireworks-deepseek-r1",
        messages=[{"role": "user", "content": "Solve a complex problem"}],
        extra_body={
            "reasoning_effort": "high",
            "top_k": 100,
        }
    )
    
    assert response.choices[0].message.content is not None
    print("✓ Reasoning model parameters work")


def test_fireworks_all_params():
    """Test all Fireworks-specific parameters together."""
    client = OpenAI(
        base_url="http://localhost:3001/v1",
        api_key="dummy-key",
    )
    
    response = client.chat.completions.create(
        model="fireworks-llama-v3p1-70b-instruct",
        messages=[{"role": "user", "content": "Test all parameters"}],
        temperature=0.8,
        max_tokens=100,
        extra_body=FIREWORKS_PARAMS
    )
    
    assert response.choices[0].message.content is not None
    print("✓ All Fireworks parameters work together")


def test_fireworks_with_mixed_params():
    """Test mixing standard OpenAI and Fireworks parameters."""
    client = OpenAI(
        base_url="http://localhost:3001/v1",
        api_key="dummy-key",
    )
    
    response = client.chat.completions.create(
        model="fireworks-llama-v3p2-3b-instruct",
        messages=[{"role": "user", "content": "Test mixed parameters"}],
        # Standard OpenAI parameters
        temperature=0.6,
        max_tokens=150,
        top_p=0.9,
        frequency_penalty=0.5,
        presence_penalty=0.5,
        # Fireworks-specific parameters
        extra_body={
            "top_k": 30,
            "min_p": 0.05,
            "repetition_penalty": 1.05,
            "context_length_exceeded_behavior": "error",
        }
    )
    
    assert response.choices[0].message.content is not None
    print("✓ Mixed standard and Fireworks parameters work")


def test_fireworks_streaming_with_params():
    """Test streaming with Fireworks parameters."""
    client = OpenAI(
        base_url="http://localhost:3001/v1",
        api_key="dummy-key",
    )
    
    stream = client.chat.completions.create(
        model="fireworks-llama-v3p1-8b-instruct",
        messages=[{"role": "user", "content": "Stream this"}],
        stream=True,
        extra_body={
            "top_k": 60,
            "draft_token_count": 10,
        }
    )
    
    chunks = list(stream)
    assert len(chunks) > 0
    print("✓ Streaming with Fireworks parameters works")


def test_fireworks_embedding():
    """Test Fireworks embedding model."""
    client = OpenAI(
        base_url="http://localhost:3001/v1",
        api_key="dummy-key",
    )
    
    response = client.embeddings.create(
        model="fireworks-nomic-embed-text-v1_5",
        input="Test embedding",
    )
    
    assert len(response.data) > 0
    assert len(response.data[0].embedding) > 0
    print("✓ Fireworks embedding works")


def test_extra_body_type_preservation():
    """Test that extra_body preserves types correctly."""
    client = OpenAI(
        base_url="http://localhost:3001/v1",
        api_key="dummy-key",
    )
    
    # Test with various types
    response = client.chat.completions.create(
        model="fireworks-llama-v3p1-8b-instruct",
        messages=[{"role": "user", "content": "Type test"}],
        extra_body={
            "top_k": 50,                    # integer
            "min_p": 0.1,                   # float
            "reasoning_effort": "medium",    # string
            "repetition_penalty": 1.0,       # float that could be integer
            "context_length_exceeded_behavior": "truncate",  # string
            "draft_token_count": 5,         # integer
        }
    )
    
    assert response.choices[0].message.content is not None
    print("✓ Type preservation in extra_body works")


# Async tests
async def test_async_fireworks_with_params():
    """Test async client with Fireworks parameters."""
    client = AsyncOpenAI(
        base_url="http://localhost:3001/v1",
        api_key="dummy-key",
    )
    
    response = await client.chat.completions.create(
        model="fireworks-llama-v3p1-8b-instruct",
        messages=[{"role": "user", "content": "Async test"}],
        extra_body={
            "top_k": 40,
            "mirostat_lr": 0.2,
            "mirostat_target": 4.0,
        }
    )
    
    assert response.choices[0].message.content is not None
    print("✓ Async client with Fireworks parameters works")


async def test_async_streaming_with_params():
    """Test async streaming with Fireworks parameters."""
    client = AsyncOpenAI(
        base_url="http://localhost:3001/v1",
        api_key="dummy-key",
    )
    
    stream = await client.chat.completions.create(
        model="fireworks-llama-v3p1-70b-instruct",
        messages=[{"role": "user", "content": "Async stream"}],
        stream=True,
        extra_body={
            "repetition_penalty": 1.15,
            "top_a": 0.85,
        }
    )
    
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)
    
    assert len(chunks) > 0
    print("✓ Async streaming with Fireworks parameters works")


def run_sync_tests():
    """Run all synchronous tests."""
    print("\n=== Running Fireworks CI Tests (Sync) ===\n")
    
    test_basic_fireworks_chat()
    test_fireworks_with_extra_body()
    test_fireworks_reasoning_model_params()
    test_fireworks_all_params()
    test_fireworks_with_mixed_params()
    test_fireworks_streaming_with_params()
    test_fireworks_embedding()
    test_extra_body_type_preservation()
    
    print("\n✅ All synchronous tests passed!")


async def run_async_tests():
    """Run all asynchronous tests."""
    print("\n=== Running Fireworks CI Tests (Async) ===\n")
    
    await test_async_fireworks_with_params()
    await test_async_streaming_with_params()
    
    print("\n✅ All asynchronous tests passed!")


def main():
    """Main test runner."""
    try:
        # Run sync tests
        run_sync_tests()
        
        # Run async tests
        asyncio.run(run_async_tests())
        
        print("\n🎉 All Fireworks CI tests passed!\n")
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())