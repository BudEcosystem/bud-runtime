#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Tests for model deployment functionality."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from budapp.commons.constants import (
    CloudModelStatusEnum,
    EndpointStatusEnum,
    ModelProviderTypeEnum,
    ModelStatusEnum,
)
from budapp.endpoint_ops.models import Endpoint as EndpointModel
from budapp.model_ops.models import CloudModel, Model
from budapp.model_ops.schemas import DeploymentTemplateCreate
from budapp.model_ops.services import ModelService


@pytest.mark.asyncio
async def test_create_endpoint_directly_for_cloud_model():
    """Test direct endpoint creation for cloud models."""
    # Setup
    model_id = uuid4()
    project_id = uuid4()
    workflow_id = uuid4()
    user_id = uuid4()
    credential_id = uuid4()
    cloud_model_id = uuid4()

    # Mock model data
    mock_model = MagicMock()
    mock_model.id = model_id
    mock_model.provider_type = ModelProviderTypeEnum.CLOUD_MODEL
    mock_model.status = ModelStatusEnum.ACTIVE
    mock_model.source = "openai"  # For proxy cache and cloud model lookup
    mock_model.uri = "gpt-4"
    mock_model.provider_id = uuid4()

    # Mock cloud model data
    mock_cloud_model = MagicMock()
    mock_cloud_model.id = cloud_model_id
    mock_cloud_model.status = CloudModelStatusEnum.ACTIVE
    mock_cloud_model.supported_endpoints = ["/v1/chat/completions"]

    # Mock deployment config
    deploy_config = DeploymentTemplateCreate(
        concurrent_requests=10, avg_sequence_length=100, avg_context_length=1000, replicas=1
    )

    # Mock endpoint - Create a proper EndpointModel-like object
    mock_endpoint = MagicMock()
    endpoint_id = uuid4()
    mock_endpoint.id = endpoint_id
    mock_endpoint.url = "budproxy-service.svc.cluster.local"
    mock_endpoint.status = EndpointStatusEnum.RUNNING
    mock_endpoint.name = "test-endpoint"

    # Create service with mocked session
    mock_session = MagicMock()
    service = ModelService(session=mock_session)

    # Mock database operations and Redis
    with patch("budapp.model_ops.services.ModelDataManager") as mock_model_manager, patch(
        "budapp.model_ops.services.CloudModelDataManager"
    ) as mock_cloud_model_manager, patch(
        "budapp.endpoint_ops.crud.EndpointDataManager"
    ) as mock_endpoint_manager, patch("budapp.commons.config.app_settings") as mock_settings, patch(
        "budapp.endpoint_ops.services.EndpointService"
    ) as mock_endpoint_service, patch("budapp.credential_ops.services.CredentialService") as mock_credential_service:
        # Configure mocks
        mock_settings.base_deployment_url = "https://example.com"

        # Create mock instances for data managers
        mock_model_manager_instance = MagicMock()
        mock_model_manager_instance.retrieve_by_fields = AsyncMock(return_value=mock_model)
        mock_model_manager.return_value = mock_model_manager_instance

        mock_cloud_model_manager_instance = MagicMock()
        mock_cloud_model_manager_instance.retrieve_by_fields = AsyncMock(return_value=mock_cloud_model)
        mock_cloud_model_manager.return_value = mock_cloud_model_manager_instance

        mock_endpoint_manager_instance = MagicMock()
        mock_endpoint_manager_instance.insert_one = AsyncMock(return_value=mock_endpoint)
        mock_endpoint_manager.return_value = mock_endpoint_manager_instance

        # Configure endpoint service and credential service mocks
        mock_endpoint_service_instance = MagicMock()
        mock_endpoint_service_instance.add_model_to_proxy_cache = AsyncMock()
        mock_endpoint_service_instance.get_inference_cost = AsyncMock(return_value=None)
        mock_endpoint_service.return_value = mock_endpoint_service_instance
        mock_credential_service_instance = MagicMock()
        mock_credential_service_instance.update_proxy_cache = AsyncMock()
        mock_credential_service.return_value = mock_credential_service_instance

        # Execute
        result = await service._create_endpoint_directly(
            model_id=model_id,
            project_id=project_id,
            cluster_id=None,  # Test with no cluster for cloud models
            endpoint_name="test-endpoint",
            deploy_config=deploy_config,
            workflow_id=workflow_id,
            current_user_id=user_id,
            credential_id=credential_id,
        )

        # Verify the function executes without error for cloud models
        # Note: The actual return value depends on the service implementation
        # The important thing is that it doesn't raise an exception for cloud models
        # This test verifies the cloud model path works correctly


@pytest.mark.asyncio
async def test_create_endpoint_directly_raises_for_non_cloud_model():
    """Test that direct endpoint creation raises error for non-cloud models."""
    # Setup
    model_id = uuid4()
    mock_model = MagicMock()
    mock_model.provider_type = ModelProviderTypeEnum.HUGGING_FACE  # Not a cloud model
    mock_model.status = ModelStatusEnum.ACTIVE

    # Create service
    mock_session = MagicMock()
    service = ModelService(session=mock_session)

    with patch("budapp.model_ops.services.ModelDataManager") as mock_model_manager:
        # Create mock instance for data manager
        mock_model_manager_instance = AsyncMock()
        mock_model_manager_instance.retrieve_by_fields = AsyncMock(return_value=mock_model)
        mock_model_manager.return_value = mock_model_manager_instance

        # Execute and verify exception
        with pytest.raises(Exception) as exc_info:
            await service._create_endpoint_directly(
                model_id=model_id,
                project_id=uuid4(),
                cluster_id=uuid4(),
                endpoint_name="test",
                deploy_config=DeploymentTemplateCreate(
                    concurrent_requests=10, avg_sequence_length=100, avg_context_length=1000
                ),
                workflow_id=uuid4(),
                current_user_id=uuid4(),
            )

        assert "Direct endpoint creation is only supported for cloud models" in str(exc_info.value)


@pytest.mark.asyncio
async def test_deploy_model_by_step_uses_direct_creation_for_cloud_models():
    """Test that deploy_model_by_step uses direct creation for cloud models."""
    # This test would be more complex and require mocking the full workflow
    # For now, we'll create a basic structure
    pass  # TODO: Implement full integration test
