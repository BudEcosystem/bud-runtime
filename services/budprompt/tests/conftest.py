"""
Pytest configuration for integration tests.
Provides fixtures for LLM configuration using environment variables.
"""

import os
import pytest
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from dotenv import load_dotenv

# Load test environment variables if .env.test exists
if os.path.exists(".env.test"):
    load_dotenv(".env.test")


@pytest.fixture(scope="session")
def llm_config():
    """
    Fixture providing LLM configuration from environment variables.

    Environment variables:
    - TEST_LLM_BASE_URL: Base URL for LLM API (default: http://20.66.97.208/v1)
    - TEST_LLM_API_KEY: API key for LLM (default: sk_)
    - TEST_LLM_MODEL_NAME: Model name (default: qwen3-32b)
    - TEST_LLM_TEMPERATURE: Temperature setting (default: 0.1)
    """
    return {
        "base_url": os.getenv("TEST_LLM_BASE_URL", "http://20.66.97.208/v1"),
        "api_key": os.getenv("TEST_LLM_API_KEY", "sk_"),
        "model_name": os.getenv("TEST_LLM_MODEL_NAME", "qwen3-32b"),
        "temperature": float(os.getenv("TEST_LLM_TEMPERATURE", "0.1")),
    }


@pytest.fixture(scope="session")
def llm_provider(llm_config):
    """
    Fixture providing configured OpenAI provider for LLM tests.
    """
    return OpenAIProvider(
        base_url=llm_config["base_url"],
        api_key=llm_config["api_key"],
    )


@pytest.fixture(scope="session")
def llm_model(llm_provider, llm_config):
    """
    Fixture providing configured OpenAI model for LLM tests.
    """
    settings = ModelSettings(temperature=llm_config["temperature"])
    return OpenAIModel(
        model_name=llm_config["model_name"],
        provider=llm_provider,
        settings=settings
    )


# Markers for different test categories
def pytest_configure(config):
    """
    Register custom markers for tests.
    """
    config.addinivalue_line(
        "markers", "ci_cd: mark test as part of CI/CD pipeline"
    )
    config.addinivalue_line(
        "markers", "timeout: mark test with a timeout in seconds (requires pytest-timeout plugin)"
    )
    config.addinivalue_line(
        "markers", "asyncio: mark test as async (handled by pytest-asyncio plugin)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "llm: mark test as requiring LLM access"
    )
