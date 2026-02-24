"""Test MLLM document support implementation."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest


# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from budapp.commons.constants import ModelEndpointEnum, ProxyProviderEnum
from budapp.endpoint_ops.schemas import BudDocConfig, ProxyModelConfig


def test_document_endpoint_exists():
    """Test that DOCUMENT endpoint is defined in ModelEndpointEnum."""
    assert hasattr(ModelEndpointEnum, "DOCUMENT")
    assert ModelEndpointEnum.DOCUMENT.value == "/v1/documents"


def test_buddoc_provider_exists():
    """Test that BUDDOC provider is defined in ProxyProviderEnum."""
    assert hasattr(ProxyProviderEnum, "BUDDOC")
    assert ProxyProviderEnum.BUDDOC.value == "buddoc"


def test_buddoc_config_creation():
    """Test that BudDocConfig can be created properly."""
    config = BudDocConfig(type="buddoc", api_base="http://test-api/v1.0/invoke/buddoc/method", model_name="test-model")

    assert config.type == "buddoc"
    assert config.api_base == "http://test-api/v1.0/invoke/buddoc/method"
    assert config.model_name == "test-model"


def test_buddoc_config_with_api_key_location():
    """Test that BudDocConfig supports api_key_location field."""
    config = BudDocConfig(
        type="buddoc",
        api_base="http://test-api/v1.0/invoke/buddoc/method",
        model_name="test-model",
        api_key_location="dynamic::authorization",
    )

    assert config.type == "buddoc"
    assert config.api_base == "http://test-api/v1.0/invoke/buddoc/method"
    assert config.model_name == "test-model"
    assert config.api_key_location == "dynamic::authorization"


@pytest.mark.asyncio
async def test_mllm_endpoints_include_document():
    """Test that MLLM models get both CHAT and DOCUMENT endpoints."""
    from budapp.commons.helpers import determine_modality_endpoints

    result = await determine_modality_endpoints("mllm")

    assert ModelEndpointEnum.CHAT in result["endpoints"]
    assert ModelEndpointEnum.DOCUMENT in result["endpoints"]
    assert len(result["endpoints"]) == 2


@pytest.mark.asyncio
async def test_proxy_cache_includes_buddoc_for_document_endpoint():
    """Test that BudDoc provider is added when DOCUMENT endpoint is present."""
    from budapp.endpoint_ops.services import EndpointService

    mock_session = Mock()
    service = EndpointService(mock_session)

    endpoint_id = uuid4()

    # Mock Redis service
    with patch("budapp.endpoint_ops.services.RedisService") as mock_redis_class:
        mock_redis = mock_redis_class.return_value
        mock_redis.set = AsyncMock()

        # Mock pricing lookup
        with patch.object(service, "get_current_pricing", return_value=None):
            # Call with DOCUMENT endpoint in supported_endpoints
            await service.add_model_to_proxy_cache(
                endpoint_id=endpoint_id,
                model_name="test-mllm-model",
                model_type="vllm",
                api_base="http://test-api",
                supported_endpoints=[ModelEndpointEnum.CHAT.value, ModelEndpointEnum.DOCUMENT.value],
                include_inference_cost=False,
            )

        # Verify Redis was called
        mock_redis.set.assert_called_once()

        # Check the stored configuration
        call_args = mock_redis.set.call_args
        cache_value = json.loads(call_args[0][1])

        model_config = cache_value[str(endpoint_id)]

        # Verify both providers are present
        assert "vllm" in model_config["routing"]
        assert "buddoc" in model_config["routing"]
        assert len(model_config["routing"]) == 2

        # Verify endpoints include both chat and document
        assert "chat" in model_config["endpoints"]
        assert "document" in model_config["endpoints"]

        # Verify BudDoc provider configuration
        assert "buddoc" in model_config["providers"]
        buddoc_config = model_config["providers"]["buddoc"]
        assert buddoc_config["type"] == "buddoc"
        assert "http://buddoc:9081" in buddoc_config["api_base"]
        # Verify api_key_location is set to forward authorization header
        assert "api_key_location" in buddoc_config
        assert buddoc_config["api_key_location"] == "dynamic::authorization"


@pytest.mark.asyncio
async def test_non_mllm_model_no_buddoc():
    """Test that non-MLLM models don't get BudDoc provider."""
    from budapp.endpoint_ops.services import EndpointService

    mock_session = Mock()
    service = EndpointService(mock_session)

    endpoint_id = uuid4()

    # Mock Redis service
    with patch("budapp.endpoint_ops.services.RedisService") as mock_redis_class:
        mock_redis = mock_redis_class.return_value
        mock_redis.set = AsyncMock()

        # Mock pricing lookup
        with patch.object(service, "get_current_pricing", return_value=None):
            # Call with only CHAT endpoint (no DOCUMENT)
            await service.add_model_to_proxy_cache(
                endpoint_id=endpoint_id,
                model_name="test-llm-model",
                model_type="vllm",
                api_base="http://test-api",
                supported_endpoints=[ModelEndpointEnum.CHAT.value],
                include_inference_cost=False,
            )

        # Check the stored configuration
        call_args = mock_redis.set.call_args
        cache_value = json.loads(call_args[0][1])

        model_config = cache_value[str(endpoint_id)]

        # Verify only VLLM provider is present
        assert "vllm" in model_config["routing"]
        assert "buddoc" not in model_config["routing"]
        assert len(model_config["routing"]) == 1

        # Verify no document endpoint
        assert "document" not in model_config["endpoints"]


if __name__ == "__main__":
    # Run basic tests that don't require async
    test_document_endpoint_exists()
    test_buddoc_provider_exists()
    test_buddoc_config_creation()

    print("✅ All basic tests passed!")
    print("\nRun with pytest for async tests:")
    print("  pytest tests/test_mllm_document_support.py -v")
