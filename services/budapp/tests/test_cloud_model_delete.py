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

"""Tests for cloud model delete functionality."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from budapp.commons.constants import (
    EndpointStatusEnum,
    ModelProviderTypeEnum,
    WorkflowStatusEnum,
)
from budapp.endpoint_ops.services import EndpointService
from budapp.endpoint_ops.crud import EndpointDataManager
from budapp.workflow_ops.crud import WorkflowDataManager, WorkflowStepDataManager
from budapp.model_ops.crud import ProviderDataManager
from budapp.credential_ops.services import CredentialService
from budapp.workflow_ops.services import WorkflowService
from budapp.model_ops.models import Provider as ProviderModel
from budapp.prompt_ops.crud import PromptVersionDataManager
from budapp.shared.notification_service import BudNotifyService


@pytest.mark.asyncio
async def test_delete_cloud_model_endpoint_immediate_deletion():
    """Test that cloud model endpoints without clusters are deleted immediately."""
    # Setup
    endpoint_id = uuid4()
    user_id = uuid4()
    project_id = uuid4()
    model_id = uuid4()
    workflow_id = uuid4()
    provider_id = uuid4()

    # Create mock objects with proper attributes
    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.name = "test-project"

    mock_model = MagicMock()
    mock_model.id = model_id
    mock_model.provider_type = ModelProviderTypeEnum.CLOUD_MODEL
    mock_model.icon = "test-icon"
    mock_model.provider_id = provider_id
    mock_model.source = "openai"
    mock_model.uri = "gpt-4"

    mock_provider = MagicMock()
    mock_provider.icon = "provider-icon"

    mock_endpoint = MagicMock()
    mock_endpoint.id = endpoint_id
    mock_endpoint.project_id = project_id
    mock_endpoint.model_id = model_id
    mock_endpoint.model = mock_model
    mock_endpoint.project = mock_project
    mock_endpoint.name = "test-endpoint"
    mock_endpoint.status = EndpointStatusEnum.RUNNING
    mock_endpoint.cluster = None
    mock_endpoint.namespace = None

    # Mock workflow data
    mock_workflow = MagicMock()
    mock_workflow.id = workflow_id
    mock_workflow.status = WorkflowStatusEnum.IN_PROGRESS
    mock_workflow.created_by = user_id

    # Create service with mocked session
    mock_session = AsyncMock()
    service = EndpointService(session=mock_session)

    # Create mock instances for data managers
    mock_endpoint_manager = AsyncMock(spec=EndpointDataManager)
    mock_workflow_manager = AsyncMock(spec=WorkflowDataManager)
    mock_workflow_step_manager = AsyncMock(spec=WorkflowStepDataManager)
    mock_provider_manager = AsyncMock(spec=ProviderDataManager)
    mock_prompt_version_manager = AsyncMock(spec=PromptVersionDataManager)
    mock_credential_service = AsyncMock(spec=CredentialService)
    mock_notify_service = AsyncMock(spec=BudNotifyService)
    mock_workflow_service = AsyncMock(spec=WorkflowService)

    # Configure mocks
    mock_endpoint_manager.retrieve_by_fields.return_value = mock_endpoint
    mock_endpoint_manager.update_by_fields.return_value = mock_endpoint
    mock_provider_manager.retrieve_by_fields.return_value = mock_provider
    mock_prompt_version_manager.get_prompt_versions_by_endpoint_id.return_value = []  # No active prompts
    mock_workflow_service.retrieve_or_create_workflow.return_value = mock_workflow
    mock_credential_service.update_proxy_cache.return_value = None
    mock_notify_service.send_notification.return_value = None

    # Update the workflow status to COMPLETED when it's updated
    async def mock_update_workflow(workflow, updates):
        if "status" in updates:
            workflow.status = updates["status"]
        return workflow
    mock_workflow_manager.update_by_fields.side_effect = mock_update_workflow

    # Mock Redis operations
    service.delete_model_from_proxy_cache = AsyncMock(return_value=None)

    # Patch the imports in the service module
    with patch('budapp.endpoint_ops.services.EndpointDataManager', return_value=mock_endpoint_manager), \
         patch('budapp.endpoint_ops.services.WorkflowDataManager', return_value=mock_workflow_manager), \
         patch('budapp.endpoint_ops.services.WorkflowStepDataManager', return_value=mock_workflow_step_manager), \
         patch('budapp.endpoint_ops.services.ProviderDataManager', return_value=mock_provider_manager), \
         patch('budapp.endpoint_ops.services.PromptVersionDataManager', return_value=mock_prompt_version_manager), \
         patch('budapp.endpoint_ops.services.CredentialService', return_value=mock_credential_service), \
         patch('budapp.endpoint_ops.services.BudNotifyService', return_value=mock_notify_service), \
         patch('budapp.endpoint_ops.services.WorkflowService', return_value=mock_workflow_service):

        # Execute
        result = await service.delete_endpoint(endpoint_id, user_id)

        # Verify
        assert result.id == workflow_id
        assert result.status == WorkflowStatusEnum.COMPLETED

        # Verify endpoint was retrieved
        mock_endpoint_manager.retrieve_by_fields.assert_called_once()

        # Verify provider was retrieved for CLOUD_MODEL
        mock_provider_manager.retrieve_by_fields.assert_called_once_with(
            ProviderModel, {"id": provider_id}
        )

        # Verify workflow was created
        mock_workflow_service.retrieve_or_create_workflow.assert_called_once()

        # Verify endpoint status was updated to DELETED
        mock_endpoint_manager.update_by_fields.assert_called()
        delete_call = None
        for call in mock_endpoint_manager.update_by_fields.call_args_list:
            if call[0][1].get("status") == EndpointStatusEnum.DELETED:
                delete_call = call
                break
        assert delete_call is not None, "Endpoint should be marked as DELETED"

        # Verify workflow status was updated to COMPLETED
        mock_workflow_manager.update_by_fields.assert_called()
        workflow_call = None
        for call in mock_workflow_manager.update_by_fields.call_args_list:
            if call[0][1].get("status") == WorkflowStatusEnum.COMPLETED:
                workflow_call = call
                break
        assert workflow_call is not None, "Workflow should be marked as COMPLETED"

        # Verify Redis cache was updated
        service.delete_model_from_proxy_cache.assert_called_once_with(endpoint_id)

        # Verify credential service was called to update proxy cache
        mock_credential_service.update_proxy_cache.assert_called_once_with(project_id)

        # Verify notification was sent
        mock_notify_service.send_notification.assert_called_once()


@pytest.mark.asyncio
async def test_delete_regular_model_endpoint_workflow_deletion():
    """Test that regular model endpoints follow the traditional workflow deletion process."""
    # Setup
    endpoint_id = uuid4()
    user_id = uuid4()
    project_id = uuid4()
    model_id = uuid4()
    workflow_id = uuid4()
    cluster_id = uuid4()
    provider_id = uuid4()

    # Create mock objects with proper attributes
    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.name = "test-project"

    mock_model = MagicMock()
    mock_model.id = model_id
    mock_model.provider_type = ModelProviderTypeEnum.HUGGING_FACE
    mock_model.icon = "test-icon"
    mock_model.provider_id = provider_id
    mock_model.source = "huggingface"
    mock_model.uri = "model-uri"

    mock_provider = MagicMock()
    mock_provider.icon = "provider-icon"

    mock_cluster = MagicMock()
    mock_cluster.cluster_id = cluster_id

    mock_endpoint = MagicMock()
    mock_endpoint.id = endpoint_id
    mock_endpoint.project_id = project_id
    mock_endpoint.model_id = model_id
    mock_endpoint.model = mock_model
    mock_endpoint.project = mock_project
    mock_endpoint.name = "test-endpoint"
    mock_endpoint.status = EndpointStatusEnum.RUNNING
    mock_endpoint.cluster = mock_cluster
    mock_endpoint.namespace = "test-namespace"

    # Mock workflow data
    mock_workflow = MagicMock()
    mock_workflow.id = workflow_id
    mock_workflow.status = WorkflowStatusEnum.IN_PROGRESS
    mock_workflow.created_by = user_id

    # Create service with mocked session
    mock_session = AsyncMock()
    service = EndpointService(session=mock_session)

    # Create mock instances for data managers
    mock_endpoint_manager = AsyncMock(spec=EndpointDataManager)
    mock_workflow_manager = AsyncMock(spec=WorkflowDataManager)
    mock_workflow_step_manager = AsyncMock(spec=WorkflowStepDataManager)
    mock_provider_manager = AsyncMock(spec=ProviderDataManager)
    mock_prompt_version_manager = AsyncMock(spec=PromptVersionDataManager)
    mock_credential_service = AsyncMock(spec=CredentialService)
    mock_workflow_service = AsyncMock(spec=WorkflowService)

    # Configure mocks
    mock_endpoint_manager.retrieve_by_fields.return_value = mock_endpoint
    mock_endpoint_manager.update_by_fields.return_value = mock_endpoint
    mock_provider_manager.retrieve_by_fields.return_value = mock_provider
    mock_prompt_version_manager.get_prompt_versions_by_endpoint_id.return_value = []  # No active prompts
    mock_workflow_service.retrieve_or_create_workflow.return_value = mock_workflow
    mock_credential_service.update_proxy_cache.return_value = None
    mock_workflow_step_manager.insert_one.return_value = None
    mock_workflow_manager.update_by_fields.return_value = mock_workflow

    # Mock Redis and cluster operations
    service.delete_model_from_proxy_cache = AsyncMock(return_value=None)
    service._perform_bud_cluster_delete_endpoint_request = AsyncMock(return_value={
        "status": "success",
        "steps": [],
        "workflow_id": str(uuid4())
    })

    # Patch the imports in the service module
    with patch('budapp.endpoint_ops.services.EndpointDataManager', return_value=mock_endpoint_manager), \
         patch('budapp.endpoint_ops.services.WorkflowDataManager', return_value=mock_workflow_manager), \
         patch('budapp.endpoint_ops.services.WorkflowStepDataManager', return_value=mock_workflow_step_manager), \
         patch('budapp.endpoint_ops.services.ProviderDataManager', return_value=mock_provider_manager), \
         patch('budapp.endpoint_ops.services.PromptVersionDataManager', return_value=mock_prompt_version_manager), \
         patch('budapp.endpoint_ops.services.CredentialService', return_value=mock_credential_service), \
         patch('budapp.endpoint_ops.services.WorkflowService', return_value=mock_workflow_service):

        # Execute
        result = await service.delete_endpoint(endpoint_id, user_id)

        # Verify
        assert result.id == workflow_id
        assert result.status == WorkflowStatusEnum.IN_PROGRESS  # Should still be in progress, not completed

        # Verify endpoint was retrieved
        mock_endpoint_manager.retrieve_by_fields.assert_called_once()

        # Verify provider was retrieved for HUGGING_FACE
        mock_provider_manager.retrieve_by_fields.assert_called_once_with(
            ProviderModel, {"id": provider_id}
        )

        # Verify workflow was created
        mock_workflow_service.retrieve_or_create_workflow.assert_called_once()

        # Verify endpoint status was updated to DELETING (not DELETED)
        mock_endpoint_manager.update_by_fields.assert_called()
        deleting_call = None
        for call in mock_endpoint_manager.update_by_fields.call_args_list:
            if call[0][1].get("status") == EndpointStatusEnum.DELETING:
                deleting_call = call
                break
        assert deleting_call is not None, "Endpoint should be marked as DELETING"

        # Verify workflow status was NOT updated to COMPLETED
        workflow_completed_call = None
        for call in mock_workflow_manager.update_by_fields.call_args_list:
            if call[0][1].get("status") == WorkflowStatusEnum.COMPLETED:
                workflow_completed_call = call
                break
        assert workflow_completed_call is None, "Workflow should NOT be marked as COMPLETED"

        # Verify bud_cluster delete was called with expected parameters
        service._perform_bud_cluster_delete_endpoint_request.assert_called_once_with(
            cluster_id, mock_endpoint.namespace, user_id, workflow_id, callback_topic=None
        )


@pytest.mark.asyncio
async def test_delete_cloud_model_endpoint_with_cluster_follows_workflow():
    """Test that cloud model endpoints with clusters follow the traditional workflow process."""
    # Setup
    endpoint_id = uuid4()
    user_id = uuid4()
    project_id = uuid4()
    model_id = uuid4()
    workflow_id = uuid4()
    cluster_id = uuid4()
    provider_id = uuid4()

    # Create mock objects with proper attributes
    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.name = "test-project"

    mock_model = MagicMock()
    mock_model.id = model_id
    mock_model.provider_type = ModelProviderTypeEnum.CLOUD_MODEL
    mock_model.icon = "test-icon"
    mock_model.provider_id = provider_id
    mock_model.source = "openai"
    mock_model.uri = "gpt-4"

    mock_provider = MagicMock()
    mock_provider.icon = "provider-icon"

    mock_cluster = MagicMock()
    mock_cluster.cluster_id = cluster_id

    mock_endpoint = MagicMock()
    mock_endpoint.id = endpoint_id
    mock_endpoint.project_id = project_id
    mock_endpoint.model_id = model_id
    mock_endpoint.model = mock_model
    mock_endpoint.project = mock_project
    mock_endpoint.name = "test-endpoint"
    mock_endpoint.status = EndpointStatusEnum.RUNNING
    mock_endpoint.cluster = mock_cluster
    mock_endpoint.namespace = "test-namespace"

    # Mock workflow data
    mock_workflow = MagicMock()
    mock_workflow.id = workflow_id
    mock_workflow.status = WorkflowStatusEnum.IN_PROGRESS
    mock_workflow.created_by = user_id

    # Create service with mocked session
    mock_session = AsyncMock()
    service = EndpointService(session=mock_session)

    # Create mock instances for data managers
    mock_endpoint_manager = AsyncMock(spec=EndpointDataManager)
    mock_workflow_manager = AsyncMock(spec=WorkflowDataManager)
    mock_workflow_step_manager = AsyncMock(spec=WorkflowStepDataManager)
    mock_provider_manager = AsyncMock(spec=ProviderDataManager)
    mock_prompt_version_manager = AsyncMock(spec=PromptVersionDataManager)
    mock_credential_service = AsyncMock(spec=CredentialService)
    mock_workflow_service = AsyncMock(spec=WorkflowService)

    # Configure mocks
    mock_endpoint_manager.retrieve_by_fields.return_value = mock_endpoint
    mock_endpoint_manager.update_by_fields.return_value = mock_endpoint
    mock_provider_manager.retrieve_by_fields.return_value = mock_provider
    mock_prompt_version_manager.get_prompt_versions_by_endpoint_id.return_value = []  # No active prompts
    mock_workflow_service.retrieve_or_create_workflow.return_value = mock_workflow
    mock_credential_service.update_proxy_cache.return_value = None
    mock_workflow_step_manager.insert_one.return_value = None
    mock_workflow_manager.update_by_fields.return_value = mock_workflow

    # Mock Redis and cluster operations
    service.delete_model_from_proxy_cache = AsyncMock(return_value=None)
    service._perform_bud_cluster_delete_endpoint_request = AsyncMock(return_value={
        "status": "success",
        "steps": [],
        "workflow_id": str(uuid4())
    })

    # Patch the imports in the service module
    with patch('budapp.endpoint_ops.services.EndpointDataManager', return_value=mock_endpoint_manager), \
         patch('budapp.endpoint_ops.services.WorkflowDataManager', return_value=mock_workflow_manager), \
         patch('budapp.endpoint_ops.services.WorkflowStepDataManager', return_value=mock_workflow_step_manager), \
         patch('budapp.endpoint_ops.services.ProviderDataManager', return_value=mock_provider_manager), \
         patch('budapp.endpoint_ops.services.PromptVersionDataManager', return_value=mock_prompt_version_manager), \
         patch('budapp.endpoint_ops.services.CredentialService', return_value=mock_credential_service), \
         patch('budapp.endpoint_ops.services.WorkflowService', return_value=mock_workflow_service):

        # Execute
        result = await service.delete_endpoint(endpoint_id, user_id)

        # Verify
        assert result.id == workflow_id
        assert result.status == WorkflowStatusEnum.IN_PROGRESS  # Should still be in progress, not completed

        # Verify endpoint was retrieved
        mock_endpoint_manager.retrieve_by_fields.assert_called_once()

        # Verify provider was retrieved for CLOUD_MODEL
        mock_provider_manager.retrieve_by_fields.assert_called_once_with(
            ProviderModel, {"id": provider_id}
        )

        # Verify workflow was created
        mock_workflow_service.retrieve_or_create_workflow.assert_called_once()

        # Verify endpoint status was updated to DELETING (not DELETED)
        mock_endpoint_manager.update_by_fields.assert_called()
        deleting_call = None
        for call in mock_endpoint_manager.update_by_fields.call_args_list:
            if call[0][1].get("status") == EndpointStatusEnum.DELETING:
                deleting_call = call
                break
        assert deleting_call is not None, "Endpoint should be marked as DELETING"

        # Verify workflow status was NOT updated to COMPLETED
        workflow_completed_call = None
        for call in mock_workflow_manager.update_by_fields.call_args_list:
            if call[0][1].get("status") == WorkflowStatusEnum.COMPLETED:
                workflow_completed_call = call
                break
        assert workflow_completed_call is None, "Workflow should NOT be marked as COMPLETED"

        # Verify bud_cluster delete was called with expected parameters
        service._perform_bud_cluster_delete_endpoint_request.assert_called_once_with(
            cluster_id, mock_endpoint.namespace, user_id, workflow_id, callback_topic=None
        )
