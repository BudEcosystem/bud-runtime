"""Test deployment settings feedback model removal Redis cache update."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status

from budapp.commons.exceptions import ClientException
from budapp.endpoint_ops.schemas import (
    DeploymentSettingsConfig,
    FallbackConfig,
    UpdateDeploymentSettingsRequest,
)
from budapp.endpoint_ops.services import EndpointService


@pytest.mark.asyncio
async def test_feedback_model_removal_updates_redis_cache():
    """Test that removing all feedback models properly updates Redis cache."""
    mock_session = MagicMock()
    service = EndpointService(session=mock_session)
    endpoint_id = uuid4()
    model_id = uuid4()
    user_id = uuid4()
    
    # Mock endpoint with existing feedback models
    mock_endpoint = MagicMock()
    mock_endpoint.id = endpoint_id
    mock_endpoint.model_id = model_id
    mock_endpoint.supported_endpoints = [MagicMock(value="chat")]
    mock_endpoint.deployment_settings = {
        "fallback_config": {
            "fallback_models": [str(uuid4()), str(uuid4())]
        }
    }
    
    # Mock model
    mock_model = MagicMock()
    mock_model.id = model_id
    mock_model.name = "test-model"
    
    # Request to remove all feedback models
    settings = UpdateDeploymentSettingsRequest(
        fallback_config=FallbackConfig(fallback_models=[])
    )
    
    with patch("budapp.endpoint_ops.services.EndpointDataManager") as mock_endpoint_manager_class, \
         patch("budapp.endpoint_ops.services.ModelDataManager") as mock_model_manager_class, \
         patch("budapp.endpoint_ops.services.RedisService") as mock_redis_class, \
         patch("budapp.endpoint_ops.services.BudNotifyService") as mock_notify_class:
        
        # Setup notification service mock
        mock_notify = MagicMock()
        mock_notify.send_notification = AsyncMock()
        mock_notify_class.return_value = mock_notify
        
        # Setup endpoint manager mock
        mock_endpoint_manager = MagicMock()
        mock_endpoint_manager.retrieve_by_fields = AsyncMock(return_value=mock_endpoint)
        mock_endpoint_manager.update_by_fields = AsyncMock(return_value=mock_endpoint)
        mock_endpoint_manager_class.return_value = mock_endpoint_manager
        
        # Setup model manager mock
        mock_model_manager = MagicMock()
        mock_model_manager.retrieve_by_fields = AsyncMock(return_value=mock_model)
        mock_model_manager_class.return_value = mock_model_manager
        
        # Setup Redis mock
        mock_redis = MagicMock()
        
        # Mock existing cache data with fallback_models
        existing_cache_data = {
            str(endpoint_id): {
                "routing": [],
                "endpoints": ["chat"],
                "providers": {},
                "fallback_models": [str(uuid4()), str(uuid4())],
                "rate_limits": {"requests_per_second": 10}
            }
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(existing_cache_data))
        mock_redis.set = AsyncMock()
        mock_redis_class.return_value = mock_redis
        
        # Execute the update
        result = await service.update_deployment_settings(endpoint_id, settings, user_id)
        
        # Verify the result
        assert result.fallback_config.fallback_models == []
        
        # Verify Redis was updated
        mock_redis.set.assert_called_once()
        cache_key, cache_value = mock_redis.set.call_args[0]
        
        assert cache_key == f"model_table:{endpoint_id}"
        
        # Parse the cached data
        cached_data = json.loads(cache_value)
        endpoint_data = cached_data[str(endpoint_id)]
        
        # Verify fallback_models key was removed
        assert "fallback_models" not in endpoint_data
        
        # Verify other data remains intact
        assert endpoint_data["routing"] == []
        assert endpoint_data["endpoints"] == ["chat"]
        assert endpoint_data["providers"] == {}
        assert endpoint_data["rate_limits"]["requests_per_second"] == 10


@pytest.mark.asyncio
async def test_feedback_model_addition_updates_redis_cache():
    """Test that adding feedback models properly updates Redis cache."""
    mock_session = MagicMock()
    service = EndpointService(session=mock_session)
    endpoint_id = uuid4()
    model_id = uuid4()
    user_id = uuid4()
    fallback_id1 = uuid4()
    fallback_id2 = uuid4()
    
    # Mock endpoint without feedback models
    mock_endpoint = MagicMock()
    mock_endpoint.id = endpoint_id
    mock_endpoint.model_id = model_id
    mock_endpoint.supported_endpoints = [MagicMock(value="chat")]
    mock_endpoint.deployment_settings = {}
    mock_endpoint.status = "RUNNING"
    
    # Mock model
    mock_model = MagicMock()
    mock_model.id = model_id
    mock_model.name = "test-model"
    
    # Import the status enum
    from budapp.endpoint_ops.models import EndpointStatusEnum
    
    # Mock fallback endpoints
    mock_fallback1 = MagicMock()
    mock_fallback1.id = fallback_id1
    mock_fallback1.project_id = mock_endpoint.project_id
    mock_fallback1.status = EndpointStatusEnum.RUNNING
    
    mock_fallback2 = MagicMock()
    mock_fallback2.id = fallback_id2
    mock_fallback2.project_id = mock_endpoint.project_id
    mock_fallback2.status = EndpointStatusEnum.RUNNING
    
    # Request to add feedback models
    settings = UpdateDeploymentSettingsRequest(
        fallback_config=FallbackConfig(fallback_models=[str(fallback_id1), str(fallback_id2)])
    )
    
    with patch("budapp.endpoint_ops.services.EndpointDataManager") as mock_endpoint_manager_class, \
         patch("budapp.endpoint_ops.services.ModelDataManager") as mock_model_manager_class, \
         patch("budapp.endpoint_ops.services.RedisService") as mock_redis_class, \
         patch("budapp.endpoint_ops.services.BudNotifyService") as mock_notify_class:
        
        # Setup notification service mock
        mock_notify = MagicMock()
        mock_notify.send_notification = AsyncMock()
        mock_notify_class.return_value = mock_notify
        
        # Setup endpoint manager mock
        mock_endpoint_manager = MagicMock()
        
        # Mock retrieve_by_fields to return different endpoints based on ID
        async def mock_retrieve_by_fields(model_class, filters, **kwargs):
            if filters.get("id") == endpoint_id:
                return mock_endpoint
            elif filters.get("id") == fallback_id1:
                return mock_fallback1
            elif filters.get("id") == fallback_id2:
                return mock_fallback2
            return None
            
        mock_endpoint_manager.retrieve_by_fields = mock_retrieve_by_fields
        mock_endpoint_manager.update_by_fields = AsyncMock(return_value=mock_endpoint)
        mock_endpoint_manager_class.return_value = mock_endpoint_manager
        
        # Setup model manager mock
        mock_model_manager = MagicMock()
        mock_model_manager.retrieve_by_fields = AsyncMock(return_value=mock_model)
        mock_model_manager_class.return_value = mock_model_manager
        
        # Setup Redis mock
        mock_redis = MagicMock()
        
        # Mock existing cache data without fallback_models
        existing_cache_data = {
            str(endpoint_id): {
                "routing": [],
                "endpoints": ["chat"],
                "providers": {}
            }
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(existing_cache_data))
        mock_redis.set = AsyncMock()
        mock_redis_class.return_value = mock_redis
        
        # Execute the update
        result = await service.update_deployment_settings(endpoint_id, settings, user_id)
        
        # Verify the result
        assert result.fallback_config.fallback_models == [str(fallback_id1), str(fallback_id2)]
        
        # Verify Redis was updated
        mock_redis.set.assert_called_once()
        cache_key, cache_value = mock_redis.set.call_args[0]
        
        assert cache_key == f"model_table:{endpoint_id}"
        
        # Parse the cached data
        cached_data = json.loads(cache_value)
        endpoint_data = cached_data[str(endpoint_id)]
        
        # Verify fallback_models key was added
        assert "fallback_models" in endpoint_data
        assert endpoint_data["fallback_models"] == [str(fallback_id1), str(fallback_id2)]
        
        # Verify other data remains intact
        assert endpoint_data["routing"] == []
        assert endpoint_data["endpoints"] == ["chat"]
        assert endpoint_data["providers"] == {}