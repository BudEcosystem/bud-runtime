"""Tests for authentication metadata tracking in Redis cache."""

import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from budapp.credential_ops.services import CredentialService


@pytest.mark.asyncio
async def test_update_proxy_cache_with_metadata_single_key():
    """Test that update_proxy_cache includes metadata for a single API key."""
    # Setup
    mock_session = MagicMock()
    service = CredentialService(mock_session)

    project_id = uuid.uuid4()
    api_key = "test-api-key-123"
    credential_id = uuid.uuid4()
    user_id = uuid.uuid4()
    expiry = datetime.now() + timedelta(days=30)

    # Mock credential retrieval
    mock_credential = MagicMock()
    mock_credential.id = credential_id
    mock_credential.user_id = user_id
    mock_credential.key = api_key
    mock_credential.expiry = expiry

    # Mock the credential data manager
    with patch('budapp.credential_ops.services.CredentialDataManager') as mock_cdm:
        mock_cdm.return_value.retrieve_credential_by_fields = AsyncMock(return_value=mock_credential)

        # Mock endpoints and adapters
        with patch('budapp.credential_ops.services.EndpointDataManager') as mock_edm:
            mock_edm.return_value.get_all_running_endpoints = AsyncMock(return_value=[])

            with patch('budapp.credential_ops.services.AdapterDataManager') as mock_adm:
                mock_adm.return_value.get_all_adapters_in_project = AsyncMock(return_value=([], 0))

                # Mock Redis service
                with patch('budapp.credential_ops.services.RedisService') as mock_redis:
                    mock_redis_instance = MagicMock()
                    mock_redis.return_value = mock_redis_instance
                    mock_redis_instance.set = AsyncMock()

                    # Call the method
                    await service.update_proxy_cache(project_id, api_key, expiry)

                    # Verify Redis was called
                    assert mock_redis_instance.set.called
                    call_args = mock_redis_instance.set.call_args

                    # Extract and verify the cache data
                    redis_key = call_args[0][0]
                    cache_data_json = call_args[0][1]
                    cache_data = json.loads(cache_data_json)

                    # Verify Redis key format
                    assert redis_key == f"api_key:{api_key}"

                    # Verify metadata is present
                    assert "__metadata__" in cache_data
                    metadata = cache_data["__metadata__"]

                    # Verify metadata fields
                    assert metadata["api_key_id"] == str(credential_id)
                    assert metadata["user_id"] == str(user_id)
                    assert metadata["api_key_project_id"] == str(project_id)


@pytest.mark.asyncio
async def test_update_proxy_cache_with_metadata_all_keys():
    """Test that update_proxy_cache includes metadata when updating all project keys."""
    # Setup
    mock_session = MagicMock()
    service = CredentialService(mock_session)

    project_id = uuid.uuid4()

    # Create multiple mock credentials
    credentials = []
    for i in range(3):
        mock_credential = MagicMock()
        mock_credential.id = uuid.uuid4()
        mock_credential.user_id = uuid.uuid4()
        mock_credential.key = f"api-key-{i}"
        mock_credential.expiry = datetime.now() + timedelta(days=30)
        credentials.append(mock_credential)

    # Mock the credential data manager
    with patch('budapp.credential_ops.services.CredentialDataManager') as mock_cdm:
        mock_cdm.return_value.get_all_credentials = AsyncMock(return_value=(credentials, len(credentials)))

        # Mock endpoints and adapters
        with patch('budapp.credential_ops.services.EndpointDataManager') as mock_edm:
            mock_edm.return_value.get_all_running_endpoints = AsyncMock(return_value=[])

            with patch('budapp.credential_ops.services.AdapterDataManager') as mock_adm:
                mock_adm.return_value.get_all_adapters_in_project = AsyncMock(return_value=([], 0))

                # Mock Redis service
                with patch('budapp.credential_ops.services.RedisService') as mock_redis:
                    mock_redis_instance = MagicMock()
                    mock_redis.return_value = mock_redis_instance
                    mock_redis_instance.set = AsyncMock()

                    # Call the method without specific API key
                    await service.update_proxy_cache(project_id)

                    # Verify Redis was called for each credential
                    assert mock_redis_instance.set.call_count == len(credentials)

                    # Verify each call has metadata
                    for i, call in enumerate(mock_redis_instance.set.call_args_list):
                        cache_data_json = call[0][1]
                        cache_data = json.loads(cache_data_json)

                        # Verify metadata exists
                        assert "__metadata__" in cache_data
                        metadata = cache_data["__metadata__"]

                        # Verify all metadata fields are present
                        assert metadata["api_key_id"] is not None
                        assert metadata["user_id"] is not None
                        assert metadata["api_key_project_id"] == str(project_id)


@pytest.mark.asyncio
async def test_update_proxy_cache_metadata_with_missing_credential():
    """Test that metadata is still included even when credential is not found."""
    # Setup
    mock_session = MagicMock()
    service = CredentialService(mock_session)

    project_id = uuid.uuid4()
    api_key = "non-existent-key"

    # Mock credential retrieval returning None
    with patch('budapp.credential_ops.services.CredentialDataManager') as mock_cdm:
        mock_cdm.return_value.retrieve_credential_by_fields = AsyncMock(return_value=None)

        # Mock endpoints and adapters
        with patch('budapp.credential_ops.services.EndpointDataManager') as mock_edm:
            mock_edm.return_value.get_all_running_endpoints = AsyncMock(return_value=[])

            with patch('budapp.credential_ops.services.AdapterDataManager') as mock_adm:
                mock_adm.return_value.get_all_adapters_in_project = AsyncMock(return_value=([], 0))

                # Mock Redis service
                with patch('budapp.credential_ops.services.RedisService') as mock_redis:
                    mock_redis_instance = MagicMock()
                    mock_redis.return_value = mock_redis_instance
                    mock_redis_instance.set = AsyncMock()

                    # Call the method
                    await service.update_proxy_cache(project_id, api_key)

                    # Verify Redis was called
                    assert mock_redis_instance.set.called
                    call_args = mock_redis_instance.set.call_args

                    # Extract and verify the cache data
                    cache_data_json = call_args[0][1]
                    cache_data = json.loads(cache_data_json)

                    # Verify metadata is present even with None values
                    assert "__metadata__" in cache_data
                    metadata = cache_data["__metadata__"]

                    # Verify metadata fields with None values
                    assert metadata["api_key_id"] is None
                    assert metadata["user_id"] is None
                    assert metadata["api_key_project_id"] == str(project_id)  # project_id is always available


@pytest.mark.asyncio
async def test_update_proxy_cache_backward_compatibility():
    """Test that models are still stored correctly alongside metadata."""
    # Setup
    mock_session = MagicMock()
    service = CredentialService(mock_session)

    project_id = uuid.uuid4()
    api_key = "test-api-key"
    endpoint_id = uuid.uuid4()
    model_id = uuid.uuid4()
    adapter_id = uuid.uuid4()
    adapter_model_id = uuid.uuid4()

    # Mock credential
    mock_credential = MagicMock()
    mock_credential.id = uuid.uuid4()
    mock_credential.user_id = uuid.uuid4()
    mock_credential.key = api_key
    mock_credential.expiry = None

    # Mock endpoint
    mock_endpoint = MagicMock()
    mock_endpoint.id = endpoint_id
    mock_endpoint.name = "test-endpoint"
    mock_endpoint.model_id = model_id
    mock_endpoint.project_id = project_id

    # Mock adapter
    mock_adapter = MagicMock()
    mock_adapter.id = adapter_id
    mock_adapter.name = "test-adapter"
    mock_adapter.model_id = adapter_model_id

    with patch('budapp.credential_ops.services.CredentialDataManager') as mock_cdm:
        mock_cdm.return_value.retrieve_credential_by_fields = AsyncMock(return_value=mock_credential)

        with patch('budapp.credential_ops.services.EndpointDataManager') as mock_edm:
            mock_edm.return_value.get_all_running_endpoints = AsyncMock(return_value=[mock_endpoint])

            with patch('budapp.credential_ops.services.AdapterDataManager') as mock_adm:
                mock_adm.return_value.get_all_adapters_in_project = AsyncMock(return_value=([mock_adapter], 1))

                with patch('budapp.credential_ops.services.RedisService') as mock_redis:
                    mock_redis_instance = MagicMock()
                    mock_redis.return_value = mock_redis_instance
                    mock_redis_instance.set = AsyncMock()

                    # Call the method
                    await service.update_proxy_cache(project_id, api_key)

                    # Extract cache data
                    call_args = mock_redis_instance.set.call_args
                    cache_data_json = call_args[0][1]
                    cache_data = json.loads(cache_data_json)

                    # Verify models are present
                    assert "test-endpoint" in cache_data
                    assert cache_data["test-endpoint"]["endpoint_id"] == str(endpoint_id)
                    assert cache_data["test-endpoint"]["model_id"] == str(model_id)
                    assert cache_data["test-endpoint"]["project_id"] == str(project_id)

                    assert "test-adapter" in cache_data
                    assert cache_data["test-adapter"]["endpoint_id"] == str(adapter_id)
                    assert cache_data["test-adapter"]["model_id"] == str(adapter_model_id)
                    assert cache_data["test-adapter"]["project_id"] == str(project_id)

                    # Verify metadata is also present
                    assert "__metadata__" in cache_data

                    # Verify existing code that iterates over models won't break
                    model_count = 0
                    for key, value in cache_data.items():
                        if key != "__metadata__":
                            # This is a model entry
                            assert "endpoint_id" in value
                            assert "model_id" in value
                            assert "project_id" in value
                            model_count += 1

                    assert model_count == 2  # One endpoint and one adapter
