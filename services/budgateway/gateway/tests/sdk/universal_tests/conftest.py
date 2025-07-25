"""Shared fixtures for universal tests."""

import pytest
import os
from openai import OpenAI


@pytest.fixture(scope="session")
def universal_client():
    """Create universal client for all tests."""
    return OpenAI(
        base_url=os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001") + "/v1",
        api_key=os.getenv("TENSORZERO_API_KEY", "test-api-key")
    )


@pytest.fixture
def basic_messages():
    """Get basic chat messages."""
    return [{"role": "user", "content": "Hello, world!"}]


@pytest.fixture
def multi_turn_messages():
    """Get multi-turn conversation messages."""
    return [
        {"role": "user", "content": "My name is Alice"},
        {"role": "assistant", "content": "Hello Alice! Nice to meet you."},
        {"role": "user", "content": "What's my name?"}
    ]


@pytest.fixture(params=["gpt-3.5-turbo", "claude-3-haiku-20240307", "meta-llama/Llama-3.2-3B-Instruct-Turbo"])
def cross_provider_model(request):
    """Parametrized fixture for testing across providers."""
    return request.param