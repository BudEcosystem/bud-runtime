#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Tests for deployment settings functionality."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import status

from budapp.commons.constants import (
    EndpointStatusEnum,
    ModelEndpointEnum,
    ModelStatusEnum,
    NotificationTypeEnum,
)
from budapp.commons.exceptions import ClientException
from budapp.endpoint_ops.models import Endpoint as EndpointModel
from budapp.endpoint_ops.schemas import (
    DeploymentSettingsConfig,
    FallbackConfig,
    RateLimitConfig,
    RetryConfig,
    UpdateDeploymentSettingsRequest,
)
from budapp.endpoint_ops.services import EndpointService
from budapp.model_ops.models import Model as ModelModel


@pytest.mark.asyncio
async def test_rate_limit_config_validation():
    """Test RateLimitConfig validation."""
    # Valid config
    config = RateLimitConfig(
        algorithm="token_bucket",
        requests_per_second=10,
        requests_per_minute=600,
        burst_size=20,
    )
    assert config.algorithm == "token_bucket"
    assert config.requests_per_second == 10
    assert config.enabled is True

    # Invalid algorithm
    with pytest.raises(ValueError, match="Algorithm must be one of"):
        RateLimitConfig(algorithm="invalid_algorithm")

    # Invalid rate values
    with pytest.raises(ValueError, match="Rate limit values must be positive"):
        RateLimitConfig(requests_per_second=0)

    with pytest.raises(ValueError, match="Rate limit values must be positive"):
        RateLimitConfig(requests_per_minute=-1)


@pytest.mark.asyncio
async def test_retry_config_validation():
    """Test RetryConfig validation."""
    # Valid config
    config = RetryConfig(num_retries=3, max_delay_s=5.0)
    assert config.num_retries == 3
    assert config.max_delay_s == 5.0

    # Invalid retries
    with pytest.raises(ValueError, match="Number of retries cannot be negative"):
        RetryConfig(num_retries=-1)

    with pytest.raises(ValueError, match="Number of retries cannot exceed 10"):
        RetryConfig(num_retries=11)

    # Invalid delay
    with pytest.raises(ValueError, match="Max delay must be positive"):
        RetryConfig(max_delay_s=0)

    with pytest.raises(ValueError, match="Max delay cannot exceed 60 seconds"):
        RetryConfig(max_delay_s=61)


@pytest.mark.asyncio
async def test_fallback_config_validation():
    """Test FallbackConfig validation."""
    # Valid config
    config = FallbackConfig(fallback_models=["model1", "model2"])
    assert config.fallback_models == ["model1", "model2"]

    # Too many fallback models
    with pytest.raises(ValueError, match="Cannot have more than 5 fallback models"):
        FallbackConfig(fallback_models=["model1", "model2", "model3", "model4", "model5", "model6"])


@pytest.mark.asyncio
async def test_get_deployment_settings_endpoint_not_found():
    """Test getting deployment settings when endpoint doesn't exist."""
    mock_session = MagicMock()
    service = EndpointService(session=mock_session)
    endpoint_id = uuid4()

    with patch("budapp.endpoint_ops.services.EndpointDataManager") as mock_endpoint_manager_class:
        mock_endpoint_manager = MagicMock()
        mock_endpoint_manager.retrieve_by_fields = AsyncMock(return_value=None)
        mock_endpoint_manager_class.return_value = mock_endpoint_manager

        with pytest.raises(ClientException) as exc_info:
            await service.get_deployment_settings(endpoint_id)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert f"Endpoint with id {endpoint_id} not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_deployment_settings_default_values():
    """Test getting deployment settings returns defaults when not configured."""
    mock_session = MagicMock()
    service = EndpointService(session=mock_session)
    endpoint_id = uuid4()

    # Mock endpoint without deployment settings
    mock_endpoint = MagicMock()
    mock_endpoint.id = endpoint_id
    mock_endpoint.deployment_settings = {}

    with patch("budapp.endpoint_ops.services.EndpointDataManager") as mock_endpoint_manager_class:
        mock_endpoint_manager = MagicMock()
        mock_endpoint_manager.retrieve_by_fields = AsyncMock(return_value=mock_endpoint)
        mock_endpoint_manager_class.return_value = mock_endpoint_manager

        settings = await service.get_deployment_settings(endpoint_id)

        assert isinstance(settings, DeploymentSettingsConfig)
        assert settings.rate_limits is None
        assert settings.retry_config is None
        assert settings.fallback_config is None


@pytest.mark.asyncio
async def test_get_deployment_settings_with_existing_config():
    """Test getting deployment settings when configured."""
    mock_session = MagicMock()
    service = EndpointService(session=mock_session)
    endpoint_id = uuid4()

    # Mock endpoint with deployment settings
    mock_endpoint = MagicMock()
    mock_endpoint.id = endpoint_id
    mock_endpoint.deployment_settings = {
        "rate_limits": {
            "algorithm": "token_bucket",
            "requests_per_second": 10,
            "enabled": True,
        },
        "retry_config": {
            "num_retries": 3,
            "max_delay_s": 5.0,
        },
    }

    with patch("budapp.endpoint_ops.services.EndpointDataManager") as mock_endpoint_manager_class:
        mock_endpoint_manager = MagicMock()
        mock_endpoint_manager.retrieve_by_fields = AsyncMock(return_value=mock_endpoint)
        mock_endpoint_manager_class.return_value = mock_endpoint_manager

        settings = await service.get_deployment_settings(endpoint_id)

        assert isinstance(settings, DeploymentSettingsConfig)
        assert settings.rate_limits.requests_per_second == 10
        assert settings.retry_config.num_retries == 3


@pytest.mark.asyncio
async def test_update_deployment_settings_endpoint_not_found():
    """Test updating deployment settings when endpoint doesn't exist."""
    mock_session = MagicMock()
    service = EndpointService(session=mock_session)
    endpoint_id = uuid4()
    user_id = uuid4()

    settings = UpdateDeploymentSettingsRequest()

    with patch("budapp.endpoint_ops.services.EndpointDataManager") as mock_endpoint_manager_class:
        mock_endpoint_manager = MagicMock()
        mock_endpoint_manager.retrieve_by_fields = AsyncMock(return_value=None)
        mock_endpoint_manager_class.return_value = mock_endpoint_manager

        with pytest.raises(ClientException) as exc_info:
            await service.update_deployment_settings(endpoint_id, settings, user_id)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert f"Endpoint with id {endpoint_id} not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_deployment_settings_partial_update():
    """Test partial update of deployment settings."""
    mock_session = MagicMock()
    service = EndpointService(session=mock_session)
    endpoint_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()

    # Mock endpoint with existing settings
    mock_endpoint = MagicMock()
    mock_endpoint.id = endpoint_id
    mock_endpoint.project_id = project_id
    mock_endpoint.name = "test-endpoint"
    mock_endpoint.deployment_settings = {
        "rate_limits": {
            "algorithm": "token_bucket",
            "requests_per_second": 10,
            "enabled": True,
        },
        "retry_config": {
            "num_retries": 3,
            "max_delay_s": 5.0,
        },
    }

    # Only update retry config
    settings = UpdateDeploymentSettingsRequest(retry_config=RetryConfig(num_retries=5, max_delay_s=10.0))

    with patch("budapp.endpoint_ops.services.EndpointDataManager") as mock_endpoint_manager_class, patch(
        "budapp.endpoint_ops.services.ModelDataManager"
    ) as mock_model_manager_class, patch("budapp.endpoint_ops.services.RedisService") as mock_redis_class, patch(
        "budapp.endpoint_ops.services.BudNotifyService"
    ) as mock_notify_class, patch(
        "budapp.endpoint_ops.services.NotificationBuilder"
    ) as mock_notification_builder_class, patch("budapp.endpoint_ops.services.uuid4") as mock_uuid4:
        mock_endpoint_manager = MagicMock()
        mock_endpoint_manager.retrieve_by_fields = AsyncMock(return_value=mock_endpoint)
        mock_endpoint_manager.update_by_fields = AsyncMock()
        mock_endpoint_manager_class.return_value = mock_endpoint_manager

        mock_model_manager = MagicMock()
        mock_model_manager.get_all_by_fields = AsyncMock(return_value=[])
        mock_model_manager.retrieve_by_fields = AsyncMock(return_value=None)
        mock_model_manager_class.return_value = mock_model_manager

        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_redis_class.return_value = mock_redis

        mock_notify = MagicMock()
        mock_notify.send_notification = AsyncMock()
        mock_notify_class.return_value = mock_notify

        # Mock uuid4
        test_uuid = uuid4()
        mock_uuid4.return_value = test_uuid

        # Mock NotificationBuilder
        mock_builder = MagicMock()
        mock_builder.set_content = MagicMock(return_value=mock_builder)
        mock_builder.set_payload = MagicMock(return_value=mock_builder)
        mock_builder.set_notification_request = MagicMock(return_value=mock_builder)
        mock_builder.build = MagicMock(return_value=MagicMock())
        mock_notification_builder_class.return_value = mock_builder

        result = await service.update_deployment_settings(endpoint_id, settings, user_id)

        # Verify partial update
        assert result.rate_limits.requests_per_second == 10  # Unchanged
        assert result.retry_config.num_retries == 5  # Updated

        # Verify database update
        mock_endpoint_manager.update_by_fields.assert_called_once()
        update_call = mock_endpoint_manager.update_by_fields.call_args[0]
        # First argument should be the endpoint instance, second should be the fields dict
        updated_settings = update_call[1]["deployment_settings"]
        assert updated_settings["retry_config"]["num_retries"] == 5
        assert updated_settings["rate_limits"]["requests_per_second"] == 10


@pytest.mark.asyncio
async def test_update_deployment_settings_invalid_fallback_model():
    """Test updating deployment settings with invalid fallback model."""
    mock_session = MagicMock()
    service = EndpointService(session=mock_session)
    endpoint_id = uuid4()
    project_id = uuid4()
    model_id = uuid4()
    user_id = uuid4()

    # Mock endpoint
    mock_endpoint = MagicMock()
    mock_endpoint.id = endpoint_id
    mock_endpoint.project_id = project_id
    mock_endpoint.model_id = model_id
    mock_endpoint.deployment_settings = {}

    # Mock primary model
    mock_primary_model = MagicMock()
    mock_primary_model.name = "primary-model"
    mock_endpoint.model = mock_primary_model

    # Mock available models
    mock_model1 = MagicMock()
    mock_model1.name = "available-model-1"

    settings = UpdateDeploymentSettingsRequest(fallback_config=FallbackConfig(fallback_models=["nonexistent-model"]))

    with patch("budapp.endpoint_ops.services.EndpointDataManager") as mock_endpoint_manager_class, patch(
        "budapp.endpoint_ops.services.ModelDataManager"
    ) as mock_model_manager_class:
        mock_endpoint_manager = MagicMock()
        mock_endpoint_manager.retrieve_by_fields = AsyncMock(return_value=mock_endpoint)
        mock_endpoint_manager_class.return_value = mock_endpoint_manager

        mock_model_manager = MagicMock()
        mock_model_manager.get_all_by_fields = AsyncMock(return_value=[mock_model1])
        mock_model_manager_class.return_value = mock_model_manager

        with pytest.raises(ClientException) as exc_info:
            await service.update_deployment_settings(endpoint_id, settings, user_id)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid fallback endpoint ID: 'nonexistent-model' (must be a valid UUID)" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_deployment_settings_fallback_same_as_primary():
    """Test updating deployment settings with fallback model same as primary."""
    mock_session = MagicMock()
    service = EndpointService(session=mock_session)
    endpoint_id = uuid4()
    project_id = uuid4()
    model_id = uuid4()
    user_id = uuid4()

    # Mock endpoint
    mock_endpoint = MagicMock()
    mock_endpoint.id = endpoint_id
    mock_endpoint.project_id = project_id
    mock_endpoint.model_id = model_id
    mock_endpoint.deployment_settings = {}

    # Mock primary model
    mock_primary_model = MagicMock()
    mock_primary_model.name = "primary-model"
    mock_endpoint.model = mock_primary_model

    # Mock available models
    mock_model1 = MagicMock()
    mock_model1.name = "primary-model"  # Same as primary

    settings = UpdateDeploymentSettingsRequest(fallback_config=FallbackConfig(fallback_models=["primary-model"]))

    with patch("budapp.endpoint_ops.services.EndpointDataManager") as mock_endpoint_manager_class, patch(
        "budapp.endpoint_ops.services.ModelDataManager"
    ) as mock_model_manager_class:
        mock_endpoint_manager = MagicMock()
        mock_endpoint_manager.retrieve_by_fields = AsyncMock(return_value=mock_endpoint)
        mock_endpoint_manager_class.return_value = mock_endpoint_manager

        mock_model_manager = MagicMock()
        mock_model_manager.get_all_by_fields = AsyncMock(return_value=[mock_model1])
        mock_model_manager_class.return_value = mock_model_manager

        with pytest.raises(ClientException) as exc_info:
            await service.update_deployment_settings(endpoint_id, settings, user_id)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid fallback endpoint ID: 'primary-model' (must be a valid UUID)" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cache_publishing_with_deployment_settings():
    """Test cache publishing includes deployment settings in correct format."""
    mock_session = MagicMock()
    service = EndpointService(session=mock_session)
    endpoint_id = uuid4()
    model_id = uuid4()

    # Mock endpoint
    mock_endpoint = MagicMock()
    mock_endpoint.id = endpoint_id
    mock_endpoint.model_id = model_id
    mock_endpoint.supported_endpoints = [ModelEndpointEnum.CHAT, ModelEndpointEnum.COMPLETION]

    # Mock model
    mock_model = MagicMock()
    mock_model.name = "test-model"

    # Deployment settings
    settings = DeploymentSettingsConfig(
        rate_limits=RateLimitConfig(
            algorithm="token_bucket",
            requests_per_second=10,
            requests_per_minute=600,
            burst_size=20,
            enabled=True,
        ),
        retry_config=RetryConfig(num_retries=3, max_delay_s=5.0),
        fallback_config=FallbackConfig(fallback_models=["backup-model"]),
    )

    with patch("budapp.endpoint_ops.services.ModelDataManager") as mock_model_manager_class, patch(
        "budapp.endpoint_ops.services.RedisService"
    ) as mock_redis_class:
        mock_model_manager = MagicMock()
        mock_model_manager.retrieve_by_fields = AsyncMock(return_value=mock_model)
        mock_model_manager_class.return_value = mock_model_manager

        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_redis_class.return_value = mock_redis

        await service._publish_deployment_settings_to_cache(mock_endpoint, settings)

        # Verify cache was updated
        mock_redis.set.assert_called_once()
        cache_key, cache_data = mock_redis.set.call_args[0]

        assert cache_key == f"model_table:{endpoint_id}"

        import json

        cached_data = json.loads(cache_data)
        endpoint_data = cached_data[str(endpoint_id)]

        # Verify gateway format
        assert endpoint_data["fallback_models"] == ["backup-model"]
        assert endpoint_data["retry_config"]["num_retries"] == 3
        assert endpoint_data["retry_config"]["max_delay_s"] == 5.0
        assert endpoint_data["rate_limits"]["algorithm"] == "token_bucket"
        assert endpoint_data["rate_limits"]["requests_per_second"] == 10
        assert endpoint_data["rate_limits"]["enabled"] is True


@pytest.mark.asyncio
async def test_deployment_settings_config_defaults():
    """Test DeploymentSettingsConfig default values."""
    config = DeploymentSettingsConfig()

    assert config.rate_limits is None
    assert config.retry_config is None
    assert config.fallback_config is None

    # Test with partial data
    config = DeploymentSettingsConfig(rate_limits=RateLimitConfig(requests_per_second=10))

    assert config.rate_limits.requests_per_second == 10
    assert config.rate_limits.algorithm == "token_bucket"
    assert config.rate_limits.enabled is True
    assert config.retry_config is None
    assert config.fallback_config is None
