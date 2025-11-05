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

"""The endpoint ops services. Contains business logic for endpoint ops."""

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4


if TYPE_CHECKING:
    from .schemas import DeploymentSettingsConfig, UpdateDeploymentSettingsRequest

import aiohttp
from fastapi import status

from budapp.commons import logging
from budapp.commons.db_utils import SessionMixin
from budapp.commons.schemas import BudNotificationMetadata
from budapp.project_ops.crud import ProjectDataManager
from budapp.project_ops.models import Project as ProjectModel

from ..cluster_ops.crud import ClusterDataManager
from ..cluster_ops.models import Cluster as ClusterModel
from ..cluster_ops.services import ClusterService
from ..commons.config import app_settings
from ..commons.constants import (
    APP_ICONS,
    BUD_INTERNAL_WORKFLOW,
    AdapterStatusEnum,
    BaseModelRelationEnum,
    BudServeWorkflowStepEventName,
    EndpointStatusEnum,
    ModelEndpointEnum,
    ModelProviderTypeEnum,
    ModelStatusEnum,
    NotificationTypeEnum,
    ProxyProviderEnum,
    WorkflowStatusEnum,
    WorkflowTypeEnum,
)
from ..commons.exceptions import ClientException, RedisException
from ..core.schemas import NotificationPayload, NotificationResult
from ..credential_ops.crud import ProprietaryCredentialDataManager
from ..credential_ops.models import ProprietaryCredential as ProprietaryCredentialModel
from ..credential_ops.services import CredentialService
from ..model_ops.crud import ModelDataManager, ProviderDataManager
from ..model_ops.models import Model as ModelsModel
from ..model_ops.models import Provider as ProviderModel
from ..model_ops.services import ModelServiceUtil
from ..prompt_ops.crud import PromptVersionDataManager
from ..shared.notification_service import BudNotifyService, NotificationBuilder
from ..shared.redis_service import RedisService
from ..user_ops.models import User as UserModel
from ..workflow_ops.crud import WorkflowDataManager, WorkflowStepDataManager
from ..workflow_ops.models import Workflow as WorkflowModel
from ..workflow_ops.models import WorkflowStep as WorkflowStepModel
from ..workflow_ops.schemas import WorkflowUtilCreate
from ..workflow_ops.services import WorkflowService, WorkflowStepService
from .crud import AdapterDataManager, EndpointDataManager, PublicationHistoryDataManager
from .models import Adapter as AdapterModel
from .models import DeploymentPricing
from .models import Endpoint as EndpointModel
from .schemas import (
    AddAdapterRequest,
    AddAdapterWorkflowStepData,
    AddWorkerRequest,
    AddWorkerWorkflowStepData,
    AnthropicConfig,
    AWSBedrockConfig,
    AWSSageMakerConfig,
    AzureConfig,
    BudDocConfig,
    DeepSeekConfig,
    DeploymentPricingResponse,
    EndpointCreate,
    FireworksConfig,
    GCPVertexConfig,
    GoogleAIStudioConfig,
    HyperbolicConfig,
    MistralConfig,
    ModelClusterDetail,
    OpenAIConfig,
    ProxyModelConfig,
    ProxyModelPricing,
    TogetherConfig,
    VLLMConfig,
    WorkerInfoFilter,
    XAIConfig,
)


logger = logging.get_logger(__name__)

# Build mapping from endpoint paths to names for efficient lookup
ENDPOINT_PATH_TO_NAME = {member.value: member.name.lower() for member in ModelEndpointEnum}


class EndpointService(SessionMixin):
    """Endpoint service."""

    # Default engine configuration injected into deployment_config on success
    _ENGINE_CONFIG_DEFAULTS: Dict[str, Any] = {
        "tool_calling_parser_type": "",
        "reasoning_parser_type": "",
        "chat_template": "",
        "enable_tool_calling": False,
        "enable_reasoning": False,
        "supports_lora": False,
    }

    @classmethod
    def _with_engine_configs(
        cls, deploy_config: Optional[Dict[str, Any]], engine_configs: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Ensure deployment_config contains engine_configs with default keys.

        Existing values in deploy_config["engine_configs"] or provided engine_configs take precedence over defaults.
        """
        base: Dict[str, Any] = dict(deploy_config or {})
        existing: Dict[str, Any] = dict((base.get("engine_configs") or {}))
        provided: Dict[str, Any] = dict(engine_configs or {})
        merged_engine = {**cls._ENGINE_CONFIG_DEFAULTS, **existing, **provided}
        base["engine_configs"] = merged_engine
        return base

    async def get_all_endpoints(
        self,
        current_user_id: UUID,
        is_superuser: bool,
        project_id: Optional[UUID],
        offset: int = 0,
        limit: int = 10,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[EndpointModel], int]:
        """Get all active endpoints.

        Args:
            current_user_id: The ID of the current user making the request
            is_superuser: Whether the current user is a superuser
            project_id: Optional project ID to filter endpoints
            offset: Pagination offset
            limit: Pagination limit
            filters: Additional filters to apply
            order_by: Ordering fields
            search: Whether to perform search

        Returns:
            Tuple of endpoint list and total count
        """
        if search:
            # Only include name, exclude other filters
            # Otherwise it will perform global search on all fields
            filters.pop("status", None)

        # Superusers can access all endpoints without project restrictions
        if is_superuser:
            # If project_id is provided, validate it exists but don't check user association
            if project_id:
                await ProjectDataManager(self.session).retrieve_by_fields(ProjectModel, {"id": project_id})
            # For superusers, project_id remains as-is (None for all, or specific UUID)
        else:
            # Non-superuser access control
            if project_id:
                # Validate project_id if provided and check user has access
                await ProjectDataManager(self.session).retrieve_by_fields(ProjectModel, {"id": project_id})

                # Check if user is associated with the project
                is_user_in_project = await ProjectDataManager(self.session).is_user_in_project(
                    current_user_id, project_id
                )
                if not is_user_in_project:
                    from ..commons.exceptions import ClientException

                    raise ClientException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        message="Access denied: You are not authorized to access this project",
                    )
            else:
                # If no project_id provided, get all projects user has access to
                user_project_ids = await ProjectDataManager(self.session).get_user_project_ids(current_user_id)
                # Set project_id to user_project_ids to filter endpoints
                project_id = user_project_ids

        return await EndpointDataManager(self.session).get_all_active_endpoints(
            project_id, offset, limit, filters, order_by, search
        )

    async def delete_endpoint(self, endpoint_id: UUID, current_user_id: UUID) -> WorkflowModel:
        """Delete an endpoint by its ID."""
        db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel, {"id": endpoint_id}, exclude_fields={"status": EndpointStatusEnum.DELETED}
        )

        if db_endpoint.status == EndpointStatusEnum.DELETING:
            raise ClientException("Deployment is already deleting")

        # Check if any active prompts are using this endpoint
        prompt_versions = await PromptVersionDataManager(self.session).get_prompt_versions_by_endpoint_id(endpoint_id)
        if prompt_versions:
            prompt_names = [f"{pv.prompt.name}" for pv in prompt_versions]
            raise ClientException(
                f"Cannot delete deployment. It is being used by prompt '{prompt_names[0]}'",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if db_endpoint.model.provider_type in [ModelProviderTypeEnum.HUGGING_FACE, ModelProviderTypeEnum.CLOUD_MODEL]:
            db_provider = await ProviderDataManager(self.session).retrieve_by_fields(
                ProviderModel, {"id": db_endpoint.model.provider_id}
            )
            model_icon = db_provider.icon
        else:
            model_icon = db_endpoint.model.icon

        current_step_number = 1

        # Retrieve or create workflow
        workflow_create = WorkflowUtilCreate(
            workflow_type=WorkflowTypeEnum.ENDPOINT_DELETION,
            title=db_endpoint.name,
            total_steps=current_step_number,
            icon=model_icon,
            tag=db_endpoint.project.name,
        )
        db_workflow = await WorkflowService(self.session).retrieve_or_create_workflow(
            workflow_id=None, workflow_data=workflow_create, current_user_id=current_user_id
        )
        logger.debug(f"Delete endpoint workflow {db_workflow.id} created")

        # Check if this is a cloud model without cluster - handle immediate deletion
        is_cloud_model = db_endpoint.model.provider_type == ModelProviderTypeEnum.CLOUD_MODEL
        has_cluster = db_endpoint.cluster and db_endpoint.cluster.cluster_id

        if is_cloud_model and not has_cluster:
            # For cloud models without cluster, perform immediate deletion
            logger.debug(f"Performing immediate deletion for cloud model endpoint {db_endpoint.id}")

            # Delete endpoint details from redis
            try:
                await self.delete_model_from_proxy_cache(db_endpoint.id)
                await CredentialService(self.session).update_proxy_cache(db_endpoint.project_id)
                await self.update_published_model_cache()
                logger.debug(f"Updated proxy cache for project {db_endpoint.project_id}")
            except (RedisException, Exception) as e:
                logger.error(f"Failed to delete endpoint details from redis: {e}")

            # Mark endpoint as deleted immediately
            await EndpointDataManager(self.session).update_by_fields(
                db_endpoint, {"status": EndpointStatusEnum.DELETED}
            )
            logger.debug(f"Cloud model endpoint {db_endpoint.id} marked as deleted")

            # Mark workflow as completed
            await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"status": WorkflowStatusEnum.COMPLETED}
            )
            logger.debug(f"Workflow {db_workflow.id} marked as completed")

            # Send notification to workflow creator
            notification_request = (
                NotificationBuilder()
                .set_content(
                    title=db_endpoint.name,
                    message="Deployment Deleted",
                    icon=model_icon,
                    result=NotificationResult(target_id=db_endpoint.project.id, target_type="project").model_dump(
                        exclude_none=True, exclude_unset=True
                    ),
                )
                .set_payload(
                    workflow_id=str(db_workflow.id), type=NotificationTypeEnum.DEPLOYMENT_DELETION_SUCCESS.value
                )
                .set_notification_request(subscriber_ids=[str(db_workflow.created_by)])
                .build()
            )
            await BudNotifyService().send_notification(notification_request)

            return db_workflow

        # For non-cloud models or cloud models with cluster, follow the existing workflow process
        try:
            # Perform delete endpoint request to bud_cluster app
            if has_cluster:
                bud_cluster_response = await self._perform_bud_cluster_delete_endpoint_request(
                    db_endpoint.cluster.cluster_id, db_endpoint.namespace, current_user_id, db_workflow.id
                )
            else:
                # For cloud models without cluster, skip bud_cluster deletion
                bud_cluster_response = {"status": "success", "message": "Cloud model endpoint deleted"}
        except ClientException as e:
            await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"status": WorkflowStatusEnum.FAILED}
            )
            raise e

        # Add payload dict to response
        for step in bud_cluster_response["steps"]:
            step["payload"] = {}

        delete_endpoint_workflow_id = bud_cluster_response.get("workflow_id")
        delete_endpoint_events = {
            BudServeWorkflowStepEventName.DELETE_ENDPOINT_EVENTS.value: bud_cluster_response,
            "delete_endpoint_workflow_id": delete_endpoint_workflow_id,
            "endpoint_id": str(db_endpoint.id),
        }

        # Insert step details in db
        await WorkflowStepDataManager(self.session).insert_one(
            WorkflowStepModel(
                workflow_id=db_workflow.id,
                step_number=current_step_number,
                data=delete_endpoint_events,
            )
        )
        logger.debug(f"Created workflow step {current_step_number} for workflow {db_workflow.id}")

        # Update progress in workflow
        bud_cluster_response["progress_type"] = BudServeWorkflowStepEventName.DELETE_ENDPOINT_EVENTS.value
        await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"progress": bud_cluster_response, "current_step": current_step_number}
        )

        # Update endpoint status to deleting
        await EndpointDataManager(self.session).update_by_fields(db_endpoint, {"status": EndpointStatusEnum.DELETING})
        logger.debug(f"Endpoint {db_endpoint.id} status updated to {EndpointStatusEnum.DELETING.value}")

        # Delete endpoint details from cache
        try:
            await self.delete_model_from_proxy_cache(db_endpoint.id)
            await CredentialService(self.session).update_proxy_cache(db_endpoint.project_id)
            await self.update_published_model_cache()
            logger.debug(f"Updated proxy cache for project {db_endpoint.project_id}")
        except (RedisException, Exception) as e:
            logger.error(f"Failed to delete endpoint details from redis: {e}")

        return db_workflow

    async def _perform_bud_cluster_delete_endpoint_request(
        self, bud_cluster_id: Optional[UUID], namespace: str, current_user_id: UUID, workflow_id: UUID
    ) -> Dict:
        """Perform delete endpoint request to bud_cluster app.

        Args:
            bud_cluster_id: The ID of the cluster being served by the endpoint to delete.
            namespace: The namespace of the cluster endpoint to delete.
        """
        if not bud_cluster_id:
            logger.warning(
                f"Skipping bud cluster delete request - no bud_cluster_id provided for namespace {namespace}"
            )
            return {}
        delete_endpoint_url = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}/method/deployment/delete"
        )

        payload = {
            "cluster_id": str(bud_cluster_id),
            "namespace": namespace,
            "notification_metadata": {
                "name": BUD_INTERNAL_WORKFLOW,
                "subscriber_ids": str(current_user_id),
                "workflow_id": str(workflow_id),
            },
            "source_topic": f"{app_settings.source_topic}",
        }

        logger.debug(f"Performing delete endpoint request to budcluster {payload}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(delete_endpoint_url, json=payload) as response:
                    response_data = await response.json()
                    if response.status != 200 or response_data.get("object") == "error":
                        logger.error(f"Failed to delete endpoint: {response.status} {response_data}")
                        raise ClientException("Failed to delete endpoint")

                    logger.debug("Successfully deleted endpoint from budcluster")
                    return response_data
        except Exception as e:
            logger.exception(f"Failed to send delete endpoint request: {e}")
            raise ClientException("Failed to delete endpoint") from e

    async def delete_endpoint_from_notification_event(self, payload: NotificationPayload) -> None:
        """Delete a endpoint in database.

        Args:
            payload: The payload to delete the endpoint with.

        Raises:
            ClientException: If the endpoint already exists.
        """
        logger.debug("Received event for deleting endpoint")

        # Get workflow and steps
        workflow_id = payload.workflow_id
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        # Define the keys required for endpoint deletion
        keys_of_interest = [
            "endpoint_id",
        ]

        # from workflow steps extract necessary information
        required_data = {}
        for db_workflow_step in db_workflow_steps:
            for key in keys_of_interest:
                if key in db_workflow_step.data:
                    required_data[key] = db_workflow_step.data[key]

        logger.debug("Collected required data from workflow steps")

        # Retrieve endpoint from db
        db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel, {"id": required_data["endpoint_id"]}, exclude_fields={"status": EndpointStatusEnum.DELETED}
        )
        logger.debug(f"Endpoint retrieved successfully: {db_endpoint.id}")

        # Mark endpoint as deleted
        db_endpoint = await EndpointDataManager(self.session).update_by_fields(
            db_endpoint, {"status": EndpointStatusEnum.DELETED}
        )
        logger.debug(f"Endpoint {db_endpoint.id} marked as deleted")

        # Mark workflow as completed
        await WorkflowDataManager(self.session).update_by_fields(db_workflow, {"status": WorkflowStatusEnum.COMPLETED})
        logger.debug(f"Workflow {db_workflow.id} marked as completed")

        # Send notification to workflow creator
        model_icon = await ModelServiceUtil(self.session).get_model_icon(db_endpoint.model)
        notification_request = (
            NotificationBuilder()
            .set_content(
                title=db_endpoint.name,
                message="Deployment Deleted",
                icon=model_icon,
                result=NotificationResult(target_id=db_endpoint.project.id, target_type="project").model_dump(
                    exclude_none=True, exclude_unset=True
                ),
            )
            .set_payload(workflow_id=str(db_workflow.id), type=NotificationTypeEnum.DEPLOYMENT_DELETION_SUCCESS.value)
            .set_notification_request(subscriber_ids=[str(db_workflow.created_by)])
            .build()
        )
        await BudNotifyService().send_notification(notification_request)

    async def create_endpoint_from_notification_event(self, payload: NotificationPayload) -> None:
        """Create an endpoint in database.

        Args:
            payload: The payload to create the endpoint with.
        """
        logger.debug("Received event for creating endpoint")

        # Get namespace and deployment URL from event
        namespace = payload.content.result.get("namespace")
        deployment_url = payload.content.result["result"]["deployment_url"]
        credential_id = payload.content.result.get("credential_id")
        number_of_nodes = payload.content.result.get("number_of_nodes")
        total_replicas = payload.content.result["deployment_status"]["replicas"]["total"]
        node_list = payload.content.result.get("deploy_config", [])
        supported_endpoints = payload.content.result["deployment_status"].get("supported_endpoints", {})

        # Handle both list and dict formats
        if isinstance(supported_endpoints, dict):
            # Filter only enabled endpoints (where value is True)
            enabled_endpoints = [endpoint for endpoint, enabled in supported_endpoints.items() if enabled]
        else:
            # Legacy format - list of endpoint strings
            enabled_endpoints = supported_endpoints

        # Calculate the active replicas with status "Running"
        active_replicas = sum(
            1
            for worker in payload.content.result["deployment_status"]["worker_data_list"]
            if worker["status"] == "Running"
        )
        if not namespace or not deployment_url:
            logger.warning("Namespace or deployment URL is missing from event")
            return

        # Get workflow steps
        workflow_id = payload.workflow_id
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        # Define the keys required for endpoint creation
        keys_of_interest = [
            "model_id",
            "project_id",
            "cluster_id",  # bud_cluster_id
            "endpoint_name",
            "deploy_config",
            # Engine configs passed via earlier steps
            "tool_calling_parser_type",
            "reasoning_parser_type",
            "chat_template",
            "enable_tool_calling",
            "enable_reasoning",
            "supports_lora",
        ]

        # from workflow steps extract necessary information
        required_data = {}
        for db_workflow_step in db_workflow_steps:
            for key in keys_of_interest:
                if key in db_workflow_step.data:
                    required_data[key] = db_workflow_step.data[key]

        logger.debug("Collected required data from workflow steps")

        # Get cluster id (optional for cloud models)
        db_cluster = None
        if "cluster_id" in required_data and required_data["cluster_id"]:
            db_cluster = await ClusterDataManager(self.session).retrieve_by_fields(
                ClusterModel, {"cluster_id": required_data["cluster_id"]}, missing_ok=True
            )

            if not db_cluster:
                logger.error(f"Cluster with id {required_data['cluster_id']} not found")
                return

        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})

        # Check duplicate name exist in endpoints (globally, irrespective of project)
        db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel,
            fields={"name": required_data["endpoint_name"]},  # Removed project_id to make it global
            exclude_fields={"status": EndpointStatusEnum.DELETED},
            missing_ok=True,
            case_sensitive=False,
        )
        if db_endpoint:
            logger.error(f"An endpoint with name {required_data['endpoint_name']} already exists.")
            return

        # Get the model to check its capabilities
        from budapp.model_ops.crud import ModelDataManager
        from budapp.model_ops.models import Model as ModelsModel

        db_model = await ModelDataManager(self.session).retrieve_by_fields(
            ModelsModel, {"id": required_data["model_id"]}
        )

        # Merge deployment endpoints with model capabilities
        # The deployment tells us what the actual deployed model supports
        # The model tells us what additional capabilities (like document processing) are available
        merged_endpoints = set(enabled_endpoints)

        # Add model capabilities (convert to values if enum objects)
        if db_model and db_model.supported_endpoints:
            for model_ep in db_model.supported_endpoints:
                if isinstance(model_ep, ModelEndpointEnum):
                    merged_endpoints.add(model_ep.value)
                    if model_ep == ModelEndpointEnum.DOCUMENT:
                        logger.info(f"Added document endpoint support for model {db_model.name}")
                else:
                    merged_endpoints.add(model_ep)
                    if model_ep == ModelEndpointEnum.DOCUMENT.value:
                        logger.info(f"Added document endpoint support for model {db_model.name}")

        # Convert back to list
        enabled_endpoints = list(merged_endpoints)
        logger.debug(f"Final supported endpoints for endpoint: {enabled_endpoints}")

        # Create endpoint in database
        # Normalize deployment config with engine configs (merge defaults with provided values)
        engine_cfg_input = {}
        for k in (
            "tool_calling_parser_type",
            "reasoning_parser_type",
            "chat_template",
            "enable_tool_calling",
            "enable_reasoning",
            "supports_lora",
        ):
            if k in required_data:
                engine_cfg_input[k] = required_data[k]
        normalized_deploy_config = self._with_engine_configs(
            required_data["deploy_config"], engine_configs=engine_cfg_input
        )

        endpoint_data = EndpointCreate(
            model_id=required_data["model_id"],
            project_id=required_data["project_id"],
            cluster_id=db_cluster.id if db_cluster else None,
            bud_cluster_id=required_data["cluster_id"],
            name=required_data["endpoint_name"],
            url=deployment_url,
            namespace=namespace,
            status=EndpointStatusEnum.RUNNING,
            created_by=db_workflow.created_by,
            status_sync_at=datetime.now(tz=timezone.utc),
            credential_id=credential_id,
            number_of_nodes=number_of_nodes,
            active_replicas=active_replicas,
            total_replicas=total_replicas,
            deployment_config=normalized_deploy_config,
            node_list=[node["name"] for node in node_list],
            supported_endpoints=enabled_endpoints,
        )

        db_endpoint = await EndpointDataManager(self.session).insert_one(
            EndpointModel(**endpoint_data.model_dump(exclude_unset=True, exclude_none=True))
        )
        logger.debug(f"Endpoint created successfully: {db_endpoint.id}")

        # Update proxy cache for project
        await self.add_model_to_proxy_cache(
            db_endpoint.id, db_endpoint.namespace, "vllm", db_endpoint.url, enabled_endpoints
        )
        await CredentialService(self.session).update_proxy_cache(db_endpoint.project_id)
        logger.debug(f"Updated proxy cache for project {db_endpoint.project_id}")

        # Update endpoint details as next step
        # Update current step number
        current_step_number = db_workflow.current_step + 1
        workflow_current_step = current_step_number

        # Update or create next workflow step
        endpoint_details = {"endpoint_details": payload.content.result}
        db_workflow_step = await WorkflowStepService(self.session).create_or_update_next_workflow_step(
            db_workflow.id, current_step_number, endpoint_details
        )
        logger.debug(f"Upsert workflow step {db_workflow_step.id} for storing endpoint details")

        # Mark workflow as completed
        logger.debug(f"Marking workflow as completed: {workflow_id}")
        await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"status": WorkflowStatusEnum.COMPLETED, "current_step": workflow_current_step}
        )

        # Send notification to workflow creator
        model_icon = await ModelServiceUtil(self.session).get_model_icon(db_endpoint.model)
        notification_request = (
            NotificationBuilder()
            .set_content(
                title=db_endpoint.name,
                message="Deployment is Done",
                icon=model_icon,
                result=NotificationResult(target_id=db_endpoint.id, target_type="endpoint").model_dump(
                    exclude_none=True, exclude_unset=True
                ),
            )
            .set_payload(workflow_id=str(db_workflow.id), type=NotificationTypeEnum.DEPLOYMENT_SUCCESS.value)
            .set_notification_request(subscriber_ids=[str(db_workflow.created_by)])
            .build()
        )
        await BudNotifyService().send_notification(notification_request)

        # Create request to trigger endpoint status update periodic task
        is_cloud_model = db_endpoint.model.provider_type == ModelProviderTypeEnum.CLOUD_MODEL

        if db_endpoint.bud_cluster_id:
            await self._perform_endpoint_status_update_request(
                db_endpoint.bud_cluster_id, db_endpoint.namespace, is_cloud_model
            )

        return db_endpoint

    async def _perform_endpoint_status_update_request(
        self, cluster_id: UUID, namespace: str, is_cloud_model: bool
    ) -> Dict:
        """Perform update endpoint status request to bud_cluster app.

        Args:
            cluster_id: The ID of the cluster to update.
            namespace: The namespace of the cluster to update.
            current_user_id: The ID of the current user.
        """
        update_cluster_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}/method/deployment/update-deployment-status"

        try:
            payload = {
                "deployment_name": namespace,
                "cluster_id": str(cluster_id),
                "cloud_model": is_cloud_model,
            }
            logger.debug(
                f"Performing update endpoint status request. payload: {payload}, endpoint: {update_cluster_endpoint}"
            )
            async with aiohttp.ClientSession() as session:
                async with session.post(update_cluster_endpoint, json=payload) as response:
                    response_data = await response.json()
                    if response.status != 200 or response_data.get("object") == "error":
                        logger.error(f"Failed to update endpoint status: {response.status} {response_data}")
                        raise ClientException(
                            "Failed to update endpoint status", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )

                    logger.debug("Successfully updated endpoint status")
                    return response_data
        except Exception as e:
            logger.exception(f"Failed to send update endpoint status request: {e}")
            raise ClientException(
                "Failed to update endpoint status", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def update_endpoint_status_from_notification_event(self, payload: NotificationPayload) -> None:
        """Update an endpoint status in database.

        Args:
            payload: The payload to update the endpoint status with.

        Raises:
            ClientException: If the endpoint already exists.
        """
        logger.debug("Received event for updating endpoint status")

        # Get endpoint from db
        logger.debug(
            f"Retrieving endpoint with bud_cluster_id: {payload.content.result['cluster_id']} and namespace: {payload.content.result['deployment_name']}"
        )
        total_replicas = len(payload.content.result["worker_data_list"])
        logger.debug(f"Number of workers : {total_replicas}")

        # Get node list
        node_list = list(
            {
                worker["node_name"]
                for worker in payload.content.result.get("worker_data_list", [])
                if worker["status"] == "Running"
            }
        )
        logger.debug(f"Node list: {node_list}")

        # Calculate the active replicas with status "Running"
        active_replicas = sum(
            1 for worker in payload.content.result["worker_data_list"] if worker["status"] == "Running"
        )
        logger.debug(f"active replicas with status 'Running': {active_replicas}")

        db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel,
            {
                "bud_cluster_id": payload.content.result["cluster_id"],
                "namespace": payload.content.result["deployment_name"],
            },
            exclude_fields={"status": EndpointStatusEnum.DELETED},
        )
        logger.debug(f"Endpoint retrieved successfully: {db_endpoint.id}")

        # Check if endpoint is already in deleting state
        if db_endpoint.status == EndpointStatusEnum.DELETING:
            logger.error("Endpoint %s is already in deleting state", db_endpoint.id)
            raise ClientException("Endpoint is already in deleting state")

        # Update cluster status
        endpoint_status = await self._get_endpoint_status(payload.content.result["status"])
        db_endpoint = await EndpointDataManager(self.session).update_by_fields(
            db_endpoint,
            {
                "status": endpoint_status,
                "total_replicas": total_replicas,
                "active_replicas": active_replicas,
                "node_list": node_list,
            },
        )
        logger.debug(
            f"Endpoint {db_endpoint.id} status updated to {endpoint_status} and total replicas to {total_replicas}"
        )

    @staticmethod
    async def _get_endpoint_status(status: str) -> EndpointStatusEnum:
        """Get the endpoint status from the payload.

        Args:
            status: The status to get the endpoint status from.

        Returns:
            EndpointStatusEnum: The endpoint status.
        """
        if status == "ready":
            return EndpointStatusEnum.RUNNING
        elif status == "pending":
            return EndpointStatusEnum.PENDING
        elif status == "ingress_failed" or status == "failed":
            return EndpointStatusEnum.UNHEALTHY
        else:
            logger.error(f"Unknown endpoint status: {status}")
            raise ClientException(f"Unknown endpoint status: {status}")

    async def get_endpoint_workers(
        self,
        endpoint_id: UUID,
        filters: WorkerInfoFilter,
        refresh: bool,
        page: int,
        limit: int,
        order_by: List[str],
        search: bool,
    ) -> dict:
        """Get endpoint workers."""
        db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(EndpointModel, {"id": endpoint_id})
        get_workers_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}/method/deployment/worker-info"
        )
        filters_dict = filters.model_dump(exclude_none=True)
        payload = {
            "namespace": db_endpoint.namespace,
            "cluster_id": str(db_endpoint.bud_cluster_id) if db_endpoint.bud_cluster_id else "",
            "page": page,
            "limit": limit,
            "order_by": order_by or [],
            "search": str(search).lower(),
            "refresh": str(refresh).lower(),
        }
        logger.info(f"Services : payload: {payload}")
        payload.update(filters_dict)
        headers = {
            "accept": "application/json",
        }
        async with aiohttp.ClientSession() as session:  # noqa: SIM117
            async with session.get(get_workers_endpoint, params=payload, headers=headers) as response:
                response_data = await response.json()
                if response.status != 200 or response_data.get("object") == "error":
                    error_message = response_data.get("message", "Failed to get endpoint workers")
                    logger.error(f"Failed to get endpoint workers: {error_message}")
                    raise ClientException(error_message)

                logger.debug("Successfully retrieved endpoint workers")
                return response_data

    async def get_endpoint_worker_logs(self, endpoint_id: UUID, worker_id: UUID) -> Dict[str, Any]:
        """Get endpoint worker logs."""
        _ = await EndpointDataManager(self.session).retrieve_by_fields(EndpointModel, {"id": endpoint_id})
        get_worker_logs_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}/method/deployment/worker-info/{worker_id}/logs"
        headers = {
            "accept": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(get_worker_logs_endpoint, headers=headers) as response:
                response_data = await response.json()
                if response.status != 200 or response_data.get("object") == "error":
                    error_message = response_data.get("message", "Failed to get endpoint worker logs")
                    logger.error(f"Failed to get endpoint worker logs: {error_message}")
                    raise ClientException(error_message)

                logger.debug("Successfully retrieved endpoint worker logs")
                return response_data.get("logs", [])

    async def get_worker_metrics_history(self, endpoint_id: UUID, worker_id: UUID) -> Dict[str, Any]:
        """Get worker metrics history."""
        _ = await EndpointDataManager(self.session).retrieve_by_fields(EndpointModel, {"id": endpoint_id})
        get_worker_logs_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}/method/deployment/worker-info/{worker_id}/metrics"

        logger.debug(f"Getting worker metrics history for worker {worker_id} at endpoint {endpoint_id}")

        headers = {
            "accept": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(get_worker_logs_endpoint, headers=headers) as response:
                response_data = await response.json()
                if response.status != 200 or response_data.get("object") == "error":
                    error_message = response_data.get("message", "Failed to get endpoint worker metrics history")
                    logger.error(f"Failed to get endpoint worker metrics history: {error_message}")
                    raise ClientException(error_message)

                logger.debug("Successfully retrieved endpoint worker logs")
                logger.debug(f" ::METRIC:: Response data: {response_data}")
                return response_data.get("data", None)

    async def get_endpoint_worker_detail(self, endpoint_id: UUID, worker_id: UUID, reload: bool) -> dict:
        """Get endpoint worker detail."""
        _ = await EndpointDataManager(self.session).retrieve_by_fields(EndpointModel, {"id": endpoint_id})
        get_worker_detail_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}/method/deployment/worker-info/{worker_id}"
        headers = {
            "accept": "application/json",
        }
        async with aiohttp.ClientSession() as session:  # noqa: SIM117
            async with session.get(
                get_worker_detail_endpoint, headers=headers, params={"reload": str(reload).lower()}
            ) as response:
                response_data = await response.json()
                if response.status != 200 or response_data.get("object") == "error":
                    error_message = response_data.get("message", "Failed to get endpoint worker detail")
                    logger.error(f"Failed to get endpoint worker detail: {error_message}")
                    raise ClientException(error_message)

                logger.debug("Successfully retrieved endpoint worker detail")
                return response_data

    async def get_model_cluster_detail(self, endpoint_id: UUID) -> ModelClusterDetail:
        """Get model cluster detail."""
        db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(EndpointModel, {"id": endpoint_id})
        # Commented out since it is same as a db retrieve
        # model_detail_json_response = await ModelService(self.session).retrieve_model(model_id)
        # model_detail = json.loads(model_detail_json_response.body.decode("utf-8"))
        cluster_id = db_endpoint.cluster_id
        cluster_detail = None
        if cluster_id:
            cluster_detail = await ClusterService(self.session).get_cluster_details(cluster_id)

        # Get running and crashed worker count
        running_worker_count, crashed_worker_count = None, None
        if db_endpoint.bud_cluster_id:
            running_worker_count, crashed_worker_count = await self.get_endpoint_worker_count(
                db_endpoint.namespace, str(db_endpoint.bud_cluster_id)
            )

        # An endpoint always have at least one worker
        if running_worker_count == 0 and crashed_worker_count == 0:
            running_worker_count, crashed_worker_count = None, None

        return ModelClusterDetail(
            id=db_endpoint.id,
            name=db_endpoint.name,
            status=db_endpoint.status,
            model=db_endpoint.model,
            cluster=cluster_detail,
            deployment_config=db_endpoint.deployment_config,
            running_worker_count=running_worker_count,
            crashed_worker_count=crashed_worker_count,
        )

    @staticmethod
    async def get_endpoint_worker_count(namespace: str, cluster_id: str) -> Tuple[int, int]:
        """Get endpoint worker count."""
        get_workers_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}/method/deployment/worker-info"
        )
        page = 1
        PAGE_LIMIT = 20

        # Initialize worker counts
        running_worker_count = 0
        crashed_worker_count = 0

        # Fetch workers in batches
        while True:
            try:
                payload = {"namespace": namespace, "cluster_id": cluster_id, "page": page, "limit": PAGE_LIMIT}
                async with aiohttp.ClientSession() as session:
                    async with session.get(get_workers_endpoint, params=payload) as response:
                        bud_cluster_response = await response.json()
                        logger.debug("bud_cluster_response: %s", bud_cluster_response)

                        if response.status != 200 or bud_cluster_response.get("object") == "error":
                            error_message = bud_cluster_response.get("message", "Failed to get endpoint workers")
                            logger.error(f"Failed to get endpoint workers: {error_message}")
                            break

                        logger.debug("Successfully retrieved %s workers for page %s", PAGE_LIMIT, page)
                        workers_data = bud_cluster_response.get("workers", [])
            except Exception as e:
                logger.exception(
                    "Failed to fetch workers for namespace %s and cluster_id %s: %s", namespace, cluster_id, e
                )
                break

            # Count running and crashed workers
            for worker in workers_data:
                status = worker.get("status")
                if status == "Running":
                    running_worker_count += 1
                else:
                    crashed_worker_count += 1

            # Check if there are more pages
            total_pages = bud_cluster_response.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1

        return running_worker_count, crashed_worker_count

    async def delete_worker_from_notification_event(self, payload: NotificationPayload) -> None:
        """Delete a worker in database.

        Args:
            payload: The payload to delete the worker with.

        Raises:
            ClientException: If the worker already exists.
        """
        logger.debug("Received event for deleting worker")

        # Get workflow and steps
        workflow_id = payload.workflow_id
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        # Define the keys required for worker deletion
        keys_of_interest = [
            "endpoint_id",
            "worker_id",
            "worker_name",
        ]

        # from workflow steps extract necessary information
        required_data = {}
        for db_workflow_step in db_workflow_steps:
            for key in keys_of_interest:
                if key in db_workflow_step.data:
                    required_data[key] = db_workflow_step.data[key]

        logger.debug("Collected required data from workflow steps")

        db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel, {"id": required_data["endpoint_id"]}, exclude_fields={"status": EndpointStatusEnum.DELETED}
        )
        logger.debug(f"Endpoint retrieved successfully: {db_endpoint.id}")

        # Calculate concurrent request per replica and reduce it
        deployment_config = db_endpoint.deployment_config
        concurrent_requests = deployment_config["concurrent_requests"]
        total_replicas = db_endpoint.total_replicas
        concurrent_request_per_replica = concurrent_requests / total_replicas
        concurrent_request_per_replica = round(concurrent_request_per_replica)
        logger.debug(
            f"Total replicas: {total_replicas}, concurrent requests: {concurrent_requests}, concurrent request per replica: {concurrent_request_per_replica}"
        )

        updated_concurrent_requests = concurrent_requests - concurrent_request_per_replica
        updated_replica_count = total_replicas - 1
        deployment_config["concurrent_requests"] = updated_concurrent_requests
        logger.debug(
            f"Updated replica count: {updated_replica_count}, Updated concurrent requests: {updated_concurrent_requests}"
        )

        self.session.refresh(db_endpoint)
        # Update endpoint with deploy config and updated replica count
        db_endpoint = await EndpointDataManager(self.session).update_by_fields(
            db_endpoint, {"deployment_config": deployment_config, "total_replicas": updated_replica_count}
        )

        # Mark workflow as completed
        await WorkflowDataManager(self.session).update_by_fields(db_workflow, {"status": WorkflowStatusEnum.COMPLETED})
        logger.debug(f"Workflow {db_workflow.id} marked as completed")

        # Send notification to workflow creator
        model_icon = await ModelServiceUtil(self.session).get_model_icon(db_endpoint.model)
        notification_request = (
            NotificationBuilder()
            .set_content(
                title=db_endpoint.name,
                message="Worker Deleted",
                icon=model_icon,
                result=NotificationResult(target_id=db_endpoint.project.id, target_type="project").model_dump(
                    exclude_none=True, exclude_unset=True
                ),
            )
            .set_payload(workflow_id=str(db_workflow.id), type=NotificationTypeEnum.DEPLOYMENT_DELETION_SUCCESS.value)
            .set_notification_request(subscriber_ids=[str(db_workflow.created_by)])
            .build()
        )
        await BudNotifyService().send_notification(notification_request)

    async def _perform_endpoint_worker_delete_request(
        self, worker_id: UUID, workflow_id: UUID, current_user_id: UUID
    ) -> Dict:
        """Perform update endpoint status request to bud_cluster app.

        Args:
            cluster_id: The ID of the cluster to update.
            namespace: The namespace of the cluster to update.
            current_user_id: The ID of the current user.
        """
        delete_worker_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}/method/deployment/worker-info"
        )

        try:
            notification_metadata = BudNotificationMetadata(
                workflow_id=str(workflow_id),
                subscriber_ids=str(current_user_id),
                name=BUD_INTERNAL_WORKFLOW,
            )
            payload = {
                "worker_id": str(worker_id),
                "notification_metadata": notification_metadata.model_dump(mode="json"),
                "source_topic": f"{app_settings.source_topic}",
            }
            logger.debug(
                f"Performing update endpoint status request. payload: {payload}, endpoint: {delete_worker_endpoint}"
            )
            async with aiohttp.ClientSession() as session:
                async with session.delete(delete_worker_endpoint, json=payload) as response:
                    response_data = await response.json()
                    if response.status != 200 or response_data.get("object") == "error":
                        logger.error(f"Failed to delete worker: {response.status} {response_data}")
                        error_message = response_data.get("message", "Failed to delete worker")
                        raise ClientException(error_message, status_code=response.status)

                    logger.debug("Successfully deleted worker")
                    return response_data
        except ClientException as e:
            raise e
        except Exception as e:
            logger.exception(f"Failed to send delete worker request: {e}")
            raise ClientException("Failed to delete worker", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from e

    async def delete_endpoint_worker(
        self, endpoint_id: UUID, worker_id: UUID, worker_name: str, current_user_id: UUID
    ) -> None:
        """Delete a endpoint worker by its ID."""
        # To check if endpoint exists
        db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel, {"id": endpoint_id}, exclude_fields={"status": EndpointStatusEnum.DELETED}
        )
        if not db_endpoint:
            logger.error(f"Endpoint with id {endpoint_id} not found")
            raise ClientException(f"Endpoint with id {endpoint_id} not found")

        if db_endpoint.model.provider_type in [ModelProviderTypeEnum.HUGGING_FACE, ModelProviderTypeEnum.CLOUD_MODEL]:
            db_provider = await ProviderDataManager(self.session).retrieve_by_fields(
                ProviderModel, {"id": db_endpoint.model.provider_id}
            )
            model_icon = db_provider.icon
        else:
            model_icon = db_endpoint.model.icon

        current_step_number = 1

        # Retrieve or create workflow
        workflow_create = WorkflowUtilCreate(
            workflow_type=WorkflowTypeEnum.ENDPOINT_WORKER_DELETION,
            title=worker_name,
            total_steps=current_step_number,
            icon=model_icon,
            tag=db_endpoint.project.name,
        )
        db_workflow = await WorkflowService(self.session).retrieve_or_create_workflow(
            workflow_id=None, workflow_data=workflow_create, current_user_id=current_user_id
        )
        logger.debug(f"Delete worker workflow {db_workflow.id} created")

        try:
            # Perform delete endpoint request to bud_cluster app
            bud_cluster_response = await self._perform_endpoint_worker_delete_request(
                worker_id, db_workflow.id, current_user_id
            )
        except ClientException as e:
            await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"status": WorkflowStatusEnum.FAILED}
            )
            raise e

        # Add payload dict to response
        for step in bud_cluster_response["steps"]:
            step["payload"] = {}

        delete_worker_workflow_id = bud_cluster_response.get("workflow_id")
        delete_worker_events = {
            BudServeWorkflowStepEventName.DELETE_WORKER_EVENTS.value: bud_cluster_response,
            "delete_worker_workflow_id": delete_worker_workflow_id,
            "endpoint_id": str(db_endpoint.id),
            "worker_id": str(worker_id),
            "worker_name": worker_name,
        }

        # Insert step details in db
        await WorkflowStepDataManager(self.session).insert_one(
            WorkflowStepModel(
                workflow_id=db_workflow.id,
                step_number=current_step_number,
                data=delete_worker_events,
            )
        )
        logger.debug(f"Created workflow step {current_step_number} for workflow {db_workflow.id}")

        # Update progress in workflow
        bud_cluster_response["progress_type"] = BudServeWorkflowStepEventName.DELETE_WORKER_EVENTS.value
        await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"progress": bud_cluster_response, "current_step": current_step_number}
        )

        return db_workflow

    async def add_worker_to_endpoint_workflow(self, current_user_id: UUID, request: AddWorkerRequest) -> WorkflowModel:
        """Add worker to endpoint workflow."""
        # Get request data
        step_number = request.step_number
        workflow_id = request.workflow_id
        workflow_total_steps = request.workflow_total_steps
        trigger_workflow = request.trigger_workflow
        endpoint_id = request.endpoint_id
        additional_concurrency = request.additional_concurrency
        current_step_number = step_number

        # Retrieve or create workflow
        workflow_create = WorkflowUtilCreate(
            workflow_type=WorkflowTypeEnum.ADD_WORKER_TO_ENDPOINT,
            title="Add Worker to Deployment",
            total_steps=workflow_total_steps,
            icon=APP_ICONS["general"]["deployment_mono"],
            tag="Deployment",
        )
        db_workflow = await WorkflowService(self.session).retrieve_or_create_workflow(
            workflow_id, workflow_create, current_user_id
        )

        # Validate endpoint id
        project_id = None
        if endpoint_id:
            db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                EndpointModel, {"id": endpoint_id}, exclude_fields={"status": EndpointStatusEnum.DELETED}
            )

            # Get icon from provider or model
            if db_endpoint.model.provider_type in [
                ModelProviderTypeEnum.CLOUD_MODEL,
                ModelProviderTypeEnum.HUGGING_FACE,
            ]:
                db_provider = await ProviderDataManager(self.session).retrieve_by_fields(
                    ProviderModel, {"id": db_endpoint.model.provider_id}
                )
                model_icon = db_provider.icon
            else:
                model_icon = db_endpoint.model.icon

            # Update title, icon and tag on workflow
            db_workflow = await WorkflowDataManager(self.session).update_by_fields(
                db_workflow,
                {"title": db_endpoint.name, "icon": model_icon, "tag": db_endpoint.project.name},
            )

            # Assign project_id
            project_id = db_endpoint.project_id

        # Prepare workflow step data
        workflow_step_data = AddWorkerWorkflowStepData(
            endpoint_id=endpoint_id,
            additional_concurrency=additional_concurrency,
        ).model_dump(exclude_none=True, exclude_unset=True, mode="json")

        # NOTE: If endpoint_id is provided, then need to add project_id to workflow step data
        # Required for frontend integration
        if endpoint_id:
            workflow_step_data["project_id"] = str(project_id)

        # Get workflow steps
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": db_workflow.id}
        )

        # For avoiding another db call for record retrieval, storing db object while iterating over db_workflow_steps
        db_current_workflow_step = None

        if db_workflow_steps:
            for db_step in db_workflow_steps:
                # Get current workflow step
                if db_step.step_number == current_step_number:
                    db_current_workflow_step = db_step

        if db_current_workflow_step:
            logger.info(f"Workflow {db_workflow.id} step {current_step_number} already exists")

            # Update workflow step data in db
            db_workflow_step = await WorkflowStepDataManager(self.session).update_by_fields(
                db_current_workflow_step,
                {"data": workflow_step_data},
            )
            logger.info(f"Workflow {db_workflow.id} step {current_step_number} updated")
        else:
            logger.info(f"Creating workflow step {current_step_number} for workflow {db_workflow.id}")

            # Insert step details in db
            db_workflow_step = await WorkflowStepDataManager(self.session).insert_one(
                WorkflowStepModel(
                    workflow_id=db_workflow.id,
                    step_number=current_step_number,
                    data=workflow_step_data,
                )
            )

        # Update workflow current step as the highest step_number
        db_max_workflow_step_number = max(step.step_number for step in db_workflow_steps) if db_workflow_steps else 0
        workflow_current_step = max(current_step_number, db_max_workflow_step_number)
        logger.info(f"The current step of workflow {db_workflow.id} is {workflow_current_step}")

        # This will ensure workflow step number is updated to the latest step number
        db_workflow = await WorkflowDataManager(self.session).update_by_fields(
            db_workflow,
            {"current_step": workflow_current_step},
        )

        # Perform bud simulation
        if additional_concurrency:
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": db_workflow.id}
            )

            # Define the keys required for model security scan
            keys_of_interest = [
                "endpoint_id",
                "additional_concurrency",
            ]

            # from workflow steps extract necessary information
            required_data = {}
            for db_workflow_step in db_workflow_steps:
                for key in keys_of_interest:
                    if key in db_workflow_step.data:
                        required_data[key] = db_workflow_step.data[key]

            # Check if all required keys are present
            required_keys = ["endpoint_id", "additional_concurrency"]
            missing_keys = [key for key in required_keys if key not in required_data]
            if missing_keys:
                raise ClientException(f"Missing required data for bud simulation: {', '.join(missing_keys)}")

            # Perform add worker bud simulation
            try:
                await self._perform_add_worker_simulation(
                    current_step_number, required_data, db_workflow, current_user_id
                )
            except ClientException as e:
                raise e

        # Trigger workflow
        if trigger_workflow:
            # query workflow steps again to get latest data
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": db_workflow.id}
            )

            # Define the keys required for model extraction
            keys_of_interest = [
                "endpoint_id",
                "additional_concurrency",
                "simulator_id",
                "deploy_config",
            ]

            # from workflow steps extract necessary information
            required_data = {}
            for db_workflow_step in db_workflow_steps:
                for key in keys_of_interest:
                    if key in db_workflow_step.data:
                        required_data[key] = db_workflow_step.data[key]

            # Check if all required keys are present
            required_keys = ["endpoint_id", "additional_concurrency", "simulator_id", "deploy_config"]
            missing_keys = [key for key in required_keys if key not in required_data]
            if missing_keys:
                raise ClientException(f"Missing required data for add worker to deployment: {', '.join(missing_keys)}")

            try:
                # Perform add worker deployment
                await self._perform_add_worker_to_deployment(
                    current_step_number, required_data, db_workflow, current_user_id
                )
            except ClientException as e:
                raise e

        return db_workflow

    async def _perform_add_worker_simulation(
        self, current_step_number: int, data: Dict, db_workflow: WorkflowModel, current_user_id: UUID
    ) -> None:
        """Perform bud simulation."""
        db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel, {"id": data["endpoint_id"]}, exclude_fields={"status": EndpointStatusEnum.DELETED}
        )

        # Create request payload
        deployment_config = db_endpoint.deployment_config
        payload = {
            "pretrained_model_uri": db_endpoint.model.uri,
            "input_tokens": deployment_config["avg_context_length"],
            "output_tokens": deployment_config["avg_sequence_length"],
            "concurrency": data["additional_concurrency"],
            "cluster_id": str(db_endpoint.cluster.cluster_id)
            if db_endpoint.cluster
            else str(db_endpoint.bud_cluster_id),
            "notification_metadata": {
                "name": BUD_INTERNAL_WORKFLOW,
                "subscriber_ids": str(current_user_id),
                "workflow_id": str(db_workflow.id),
            },
            "source_topic": f"{app_settings.source_topic}",
        }
        if db_endpoint.model.provider_type == ModelProviderTypeEnum.CLOUD_MODEL:
            payload["target_ttft"] = 0
            payload["target_throughput_per_user"] = 0
            payload["target_e2e_latency"] = 0
            payload["is_proprietary_model"] = True
        else:
            payload["target_ttft"] = deployment_config["ttft"][0] if deployment_config["ttft"] else None
            payload["target_throughput_per_user"] = (
                deployment_config["per_session_tokens_per_sec"][1]
                if deployment_config["per_session_tokens_per_sec"]
                else None
            )
            payload["target_e2e_latency"] = (
                deployment_config["e2e_latency"][0] if deployment_config["e2e_latency"] else None
            )
            payload["is_proprietary_model"] = False

        # Perform bud simulation request
        bud_simulation_response = await self._perform_bud_simulation_request(payload)

        # Add payload dict to response
        for step in bud_simulation_response["steps"]:
            step["payload"] = {}

        simulator_id = bud_simulation_response.get("workflow_id")

        # NOTE: Dependency with recommended cluster api (GET /clusters/recommended/{workflow_id})
        # NOTE: Replace concurrent_requests with additional_concurrency
        # Required to compare with concurrent_requests in simulator response
        deployment_config["concurrent_requests"] = data["additional_concurrency"]
        bud_simulation_events = {
            "simulator_id": simulator_id,
            BudServeWorkflowStepEventName.BUD_SIMULATOR_EVENTS.value: bud_simulation_response,
            "deploy_config": deployment_config,
            "model_id": str(db_endpoint.model.id),
        }

        # Increment current step number
        current_step_number = current_step_number + 1
        workflow_current_step = current_step_number

        # Update or create next workflow step
        db_workflow_step = await WorkflowStepService(self.session).create_or_update_next_workflow_step(
            db_workflow.id, current_step_number, bud_simulation_events
        )
        logger.debug(f"Workflow step created with id {db_workflow_step.id}")

        # Update progress in workflow
        bud_simulation_response["progress_type"] = BudServeWorkflowStepEventName.BUD_SIMULATOR_EVENTS.value
        await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"progress": bud_simulation_response, "current_step": workflow_current_step}
        )

    async def _perform_bud_simulation_request(self, payload: Dict) -> Dict:
        """Perform bud simulation request."""
        bud_simulation_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_simulator_app_id}/method/simulator/run"
        )
        logger.debug(f"payload for bud simulation on add worker to endpoint : {payload}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(bud_simulation_endpoint, json=payload) as response:
                    response_data = await response.json()
                    if response.status >= 400:
                        raise ClientException("Unable to perform bud simulation")

                    return response_data
        except ClientException as e:
            raise e
        except Exception as e:
            logger.error(f"Failed to perform bud simulation request: {e}")
            raise ClientException("Unable to perform bud simulation") from e

    async def _perform_add_worker_to_deployment(
        self, current_step_number: int, data: Dict, db_workflow: WorkflowModel, current_user_id: UUID
    ) -> None:
        """Perform add worker to deployment."""
        # Get endpoint
        db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel, {"id": data["endpoint_id"]}, exclude_fields={"status": EndpointStatusEnum.DELETED}
        )
        deployment_config = db_endpoint.deployment_config

        # Model URI selection as per lite-llm updates
        db_model = db_endpoint.model
        credential_id = db_endpoint.credential_id
        if db_model.provider_type == ModelProviderTypeEnum.CLOUD_MODEL:
            model_uri = db_model.uri
            model_source = db_model.source
            if model_uri.startswith(f"{model_source}/"):
                model_uri = model_uri.removeprefix(f"{model_source}/")
            deploy_model_uri = model_uri if not credential_id else f"{model_source}/{model_uri}"
        else:
            deploy_model_uri = db_model.local_path

        add_worker_payload = {
            "cluster_id": str(db_endpoint.bud_cluster_id) if db_endpoint.bud_cluster_id else "",
            "simulator_id": data["simulator_id"],
            "endpoint_name": db_endpoint.name,
            "model": deploy_model_uri,
            "concurrency": data["additional_concurrency"],
            "input_tokens": deployment_config["avg_context_length"],
            "output_tokens": deployment_config["avg_sequence_length"],
            "target_throughput_per_user": deployment_config["per_session_tokens_per_sec"][1]
            if deployment_config.get("per_session_tokens_per_sec")
            else None,
            "target_ttft": deployment_config["ttft"][0] if deployment_config.get("ttft") else None,
            "target_e2e_latency": deployment_config["e2e_latency"][0]
            if deployment_config.get("e2e_latency")
            else None,
            "credential_id": str(db_endpoint.credential_id) if db_endpoint.credential_id else None,
            "existing_deployment_namespace": db_endpoint.namespace,
            "notification_metadata": {
                "name": BUD_INTERNAL_WORKFLOW,
                "subscriber_ids": str(current_user_id),
                "workflow_id": str(db_workflow.id),
            },
            "source_topic": f"{app_settings.source_topic}",
        }

        # Perform add worker to deployment request
        add_worker_response = await self._perform_add_worker_to_deployment_request(add_worker_payload)

        # Add payload dict to response
        for step in add_worker_response["steps"]:
            step["payload"] = {}

        add_worker_events = {BudServeWorkflowStepEventName.BUDSERVE_CLUSTER_EVENTS.value: add_worker_response}

        current_step_number = current_step_number + 1
        workflow_current_step = current_step_number

        # Update or create next workflow step
        db_workflow_step = await WorkflowStepService(self.session).create_or_update_next_workflow_step(
            db_workflow.id, current_step_number, add_worker_events
        )
        logger.debug(f"Workflow step created with id {db_workflow_step.id}")

        # Update progress in workflow
        add_worker_response["progress_type"] = BudServeWorkflowStepEventName.BUDSERVE_CLUSTER_EVENTS.value
        await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"progress": add_worker_response, "current_step": workflow_current_step}
        )

    @staticmethod
    async def _perform_add_worker_to_deployment_request(payload: Dict) -> Dict:
        """Perform add worker to deployment request."""
        add_worker_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}/method/deployment"
        )
        logger.debug(f"payload for add worker to deployment : {payload}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(add_worker_endpoint, json=payload) as response:
                    response_data = await response.json()
                    if response.status >= 400 or response_data.get("object") == "error":
                        raise ClientException("Unable to perform add worker to deployment")

                    return response_data
        except ClientException as e:
            raise e
        except Exception as e:
            logger.error(f"Failed to perform add worker to deployment request: {e}")
            raise ClientException("Unable to perform add worker to deployment") from e

    async def add_worker_from_notification_event(self, payload: NotificationPayload) -> None:
        """Add worker from notification event."""
        # Get workflow and workflow steps
        workflow_id = payload.workflow_id
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        # Define the keys required for endpoint creation
        keys_of_interest = [
            "endpoint_id",
        ]

        # from workflow steps extract necessary information
        required_data = {}
        for db_workflow_step in db_workflow_steps:
            for key in keys_of_interest:
                if key in db_workflow_step.data:
                    required_data[key] = db_workflow_step.data[key]

        logger.debug("Collected required data from workflow steps")

        # Get endpoint id
        db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel,
            {"id": required_data["endpoint_id"]},
            exclude_fields={"status": EndpointStatusEnum.DELETED},
            missing_ok=True,
        )

        if not db_endpoint:
            logger.error(f"Endpoint with id {required_data['endpoint_id']} not found")
            return

        # Add concurrency to existing deployment config
        deployment_config = db_endpoint.deployment_config
        logger.debug(f"Existing deployment config: {deployment_config}")

        existing_concurrency = deployment_config["concurrent_requests"]
        additional_concurrency = payload.content.result.get("result", {}).get("concurrency", 0)
        deployment_config["concurrent_requests"] = existing_concurrency + additional_concurrency

        # Get total replicas
        total_replicas = payload.content.result["deployment_status"]["replicas"]["total"]
        logger.debug(f"Total replicas: {total_replicas}")

        # Get Node List
        db_endpoint_node_list = db_endpoint.node_list
        add_worker_node_list = payload.content.result.get("deploy_config", [])

        self.session.refresh(db_endpoint)
        db_endpoint = await EndpointDataManager(self.session).update_by_fields(
            db_endpoint,
            {
                "deployment_config": deployment_config,
                "total_replicas": total_replicas,
                "node_list": list(set(db_endpoint_node_list + add_worker_node_list)),
            },
        )
        logger.debug(f"Updated deployment config: {deployment_config}")

        # Update current step number
        current_step_number = db_workflow.current_step + 1
        workflow_current_step = current_step_number

        execution_status_data = {
            "workflow_execution_status": {
                "status": "success",
                "message": "Deployment successfully updated with additional concurrency",
            },
        }
        # Update or create next workflow step
        db_workflow_step = await WorkflowStepService(self.session).create_or_update_next_workflow_step(
            db_workflow.id, current_step_number, execution_status_data
        )
        logger.debug(f"Upsert workflow step {db_workflow_step.id} for storing endpoint details")

        # Mark workflow as completed
        logger.debug(f"Marking workflow as completed: {workflow_id}")
        await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"status": WorkflowStatusEnum.COMPLETED, "current_step": workflow_current_step}
        )

        # Send notification to workflow creator
        model_icon = await ModelServiceUtil(self.session).get_model_icon(db_endpoint.model)

        notification_request = (
            NotificationBuilder()
            .set_content(
                title=db_endpoint.name,
                message="Worker Added",
                icon=model_icon,
                result=NotificationResult(target_id=db_endpoint.id, target_type="endpoint").model_dump(
                    exclude_none=True, exclude_unset=True
                ),
            )
            .set_payload(workflow_id=str(db_workflow.id), type=NotificationTypeEnum.DEPLOYMENT_SUCCESS.value)
            .set_notification_request(subscriber_ids=[str(db_workflow.created_by)])
            .build()
        )
        await BudNotifyService().send_notification(notification_request)

    async def add_adapter_workflow(self, current_user_id: UUID, request: AddAdapterRequest) -> None:
        """Add adapter workflow."""
        step_number = request.step_number
        workflow_id = request.workflow_id
        workflow_total_steps = request.workflow_total_steps
        endpoint_id = request.endpoint_id
        adapter_name = request.adapter_name
        adapter_model_id = request.adapter_model_id
        trigger_workflow = request.trigger_workflow

        current_step_number = step_number

        # Retrieve or create workflow
        workflow_create = WorkflowUtilCreate(
            workflow_type=WorkflowTypeEnum.ADD_ADAPTER,
            title="Add Adapter",
            total_steps=workflow_total_steps,
            icon=APP_ICONS["general"]["deployment_mono"],
            tag="Deployment",
        )
        db_workflow = await WorkflowService(self.session).retrieve_or_create_workflow(
            workflow_id, workflow_create, current_user_id
        )

        # Validate endpoint id
        project_id = None
        if endpoint_id:
            db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                EndpointModel, {"id": endpoint_id}, exclude_fields={"status": EndpointStatusEnum.DELETED}
            )

            # Get icon from provider or model
            if db_endpoint.model.provider_type in [
                ModelProviderTypeEnum.CLOUD_MODEL,
                ModelProviderTypeEnum.HUGGING_FACE,
            ]:
                db_provider = await ProviderDataManager(self.session).retrieve_by_fields(
                    ProviderModel, {"id": db_endpoint.model.provider_id}
                )
                model_icon = db_provider.icon
            else:
                model_icon = db_endpoint.model.icon

            # Update title, icon and tag on workflow
            db_workflow = await WorkflowDataManager(self.session).update_by_fields(
                db_workflow,
                {"title": db_endpoint.name, "icon": model_icon, "tag": db_endpoint.project.name},
            )

            # Assign project_id
            project_id = db_endpoint.project_id

            # Check maximum adapter limit per endpoint
            existing_adapters = await AdapterDataManager(self.session).get_all_by_fields(
                AdapterModel,
                {"endpoint_id": endpoint_id},
                exclude_fields={"status": AdapterStatusEnum.DELETED},
            )
            if len(existing_adapters) >= 5:
                raise ClientException(
                    "Maximum of 5 adapters per deployment reached. Please delete an existing adapter before adding a new one."
                )

        # validate base model id
        if adapter_model_id:
            db_model = await ModelDataManager(self.session).retrieve_by_fields(
                ModelsModel,
                {
                    "id": adapter_model_id,
                    "status": ModelStatusEnum.ACTIVE,
                    "base_model_relation": BaseModelRelationEnum.ADAPTER,
                    # "base_model": [db_endpoint.model_id],
                },
            )
            if not db_model:
                raise ClientException("Adapter model not found")

            db_adapters = await AdapterDataManager(self.session).retrieve_by_fields(
                AdapterModel,
                {"model_id": adapter_model_id, "endpoint_id": endpoint_id},
                missing_ok=True,
                exclude_fields={"status": AdapterStatusEnum.DELETED},
            )
            logger.debug(f"db_adapters: {db_adapters}")

            if db_adapters:
                raise ClientException("Adapter is already added in the endpoint")

        if adapter_name:
            db_adapters = await AdapterDataManager(self.session).retrieve_by_fields(
                AdapterModel,
                {"name": adapter_name, "endpoint_id": endpoint_id},
                missing_ok=True,
                exclude_fields={"status": AdapterStatusEnum.DELETED},
            )
            if db_adapters:
                raise ClientException("Adapter name is already taken in the endpoint")

            db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                EndpointModel,
                {"name": adapter_name, "project_id": project_id},
                missing_ok=True,
                exclude_fields={"status": EndpointStatusEnum.DELETED},
            )
            if db_endpoint:
                raise ClientException("Name already taken in the project")

        # Prepare workflow step data
        workflow_step_data = AddAdapterWorkflowStepData(
            endpoint_id=endpoint_id,
            project_id=project_id,
            adapter_name=adapter_name,
            adapter_model_id=adapter_model_id,
        ).model_dump(exclude_none=True, exclude_unset=True, mode="json")

        # NOTE: If endpoint_id is provided, then need to add project_id to workflow step data
        # Required for frontend integration
        if endpoint_id:
            workflow_step_data["project_id"] = str(project_id)

        # Get workflow steps
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": db_workflow.id}
        )

        # For avoiding another db call for record retrieval, storing db object while iterating over db_workflow_steps
        db_current_workflow_step = None

        if db_workflow_steps:
            for db_step in db_workflow_steps:
                # Get current workflow step
                if db_step.step_number == current_step_number:
                    db_current_workflow_step = db_step

        if db_current_workflow_step:
            logger.info(f"Workflow {db_workflow.id} step {current_step_number} already exists")

            # Update workflow step data in db
            db_workflow_step = await WorkflowStepDataManager(self.session).update_by_fields(
                db_current_workflow_step,
                {"data": workflow_step_data},
            )
            logger.info(f"Workflow {db_workflow.id} step {current_step_number} updated")
        else:
            logger.info(f"Creating workflow step {current_step_number} for workflow {db_workflow.id}")

            # Insert step details in db
            db_workflow_step = await WorkflowStepDataManager(self.session).insert_one(
                WorkflowStepModel(
                    workflow_id=db_workflow.id,
                    step_number=current_step_number,
                    data=workflow_step_data,
                )
            )

        # Update workflow current step as the highest step_number
        db_max_workflow_step_number = max(step.step_number for step in db_workflow_steps) if db_workflow_steps else 0
        workflow_current_step = max(current_step_number, db_max_workflow_step_number)
        logger.info(f"The current step of workflow {db_workflow.id} is {workflow_current_step}")

        # This will ensure workflow step number is updated to the latest step number
        db_workflow = await WorkflowDataManager(self.session).update_by_fields(
            db_workflow,
            {"current_step": workflow_current_step},
        )

        # Trigger workflow
        if trigger_workflow:
            # query workflow steps again to get latest data
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": db_workflow.id}
            )

            # Define the keys required for model extraction
            keys_of_interest = ["endpoint_id", "adapter_name", "adapter_model_id"]

            # from workflow steps extract necessary information
            required_data = {}
            for db_workflow_step in db_workflow_steps:
                for key in keys_of_interest:
                    if key in db_workflow_step.data:
                        required_data[key] = db_workflow_step.data[key]

            # Check if all required keys are present
            required_keys = ["endpoint_id", "adapter_name", "adapter_model_id"]
            missing_keys = [key for key in required_keys if key not in required_data]
            if missing_keys:
                raise ClientException(f"Missing required data for add worker to deployment: {', '.join(missing_keys)}")

            if not required_data["adapter_name"]:
                raise ClientException("Adapter name is required")

            db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                EndpointModel,
                {"id": required_data["endpoint_id"]},
                exclude_fields={"status": EndpointStatusEnum.DELETED},
            )
            db_model = await ModelDataManager(self.session).retrieve_by_fields(
                ModelsModel, {"id": required_data["adapter_model_id"]}
            )
            # Get base model
            required_data["adapter_model_uri"] = db_model.local_path
            required_data["namespace"] = db_endpoint.namespace
            required_data["endpoint_name"] = db_endpoint.name
            required_data["adapters"], required_data["adapter_name"] = await self._get_adapters_by_endpoint(
                db_endpoint.id,
                required_data["namespace"],
                required_data["adapter_name"],
                required_data["adapter_model_uri"],
            )

            db_cluster = None
            if db_endpoint.cluster_id:
                db_cluster = await ClusterDataManager(self.session).retrieve_by_fields(
                    ClusterModel, {"id": db_endpoint.cluster_id}
                )
                required_data["ingress_url"] = db_cluster.ingress_url
                required_data["cluster_id"] = str(db_cluster.cluster_id)
            else:
                # For cloud models without cluster
                required_data["ingress_url"] = ""
                required_data["cluster_id"] = str(db_endpoint.bud_cluster_id) if db_endpoint.bud_cluster_id else ""

            try:
                # Perform model quantization
                await self._trigger_adapter_deployment(
                    current_step_number, required_data, db_workflow, current_user_id
                )
            except ClientException as e:
                raise e

        return db_workflow

    async def _get_adapters_by_endpoint(
        self, endpoint_id: UUID, endpoint_name: str, adapter_name: str, adapter_model_uri: str, adapter_id: UUID = None
    ) -> Tuple[List[AdapterModel], str]:
        # Build exclude fields to filter out DELETED adapters and the current adapter (if specified)
        exclude_fields = {"status": AdapterStatusEnum.DELETED}
        if adapter_id:
            exclude_fields["id"] = adapter_id

        db_adapters = await AdapterDataManager(self.session).get_all_by_fields(
            AdapterModel, {"endpoint_id": endpoint_id}, exclude_fields=exclude_fields
        )

        adapters = []
        if db_adapters:
            adapters = [
                {"name": adapter.deployment_name, "artifactURL": adapter.model.local_path} for adapter in db_adapters
            ]

        deployment_name = ""
        if not adapter_id:
            deployment_name = endpoint_name + "-" + adapter_name
            adapters.append({"name": deployment_name, "artifactURL": adapter_model_uri})

        return adapters, deployment_name

    async def _trigger_adapter_deployment(
        self, current_step_number: int, data: Dict, db_workflow: WorkflowModel, current_user_id: UUID
    ) -> Dict:
        """Trigger adapter deployment."""
        # Retrieve endpoint to get deployment configuration
        db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel, {"id": data["endpoint_id"]}, exclude_fields={"status": EndpointStatusEnum.DELETED}
        )
        deployment_config = db_endpoint.deployment_config

        # Create request payload
        payload = {
            "endpoint_name": data["endpoint_name"],
            "ingress_url": data["ingress_url"],
            "adapter_path": data["adapter_model_uri"],
            "adapter_name": data["adapter_name"],
            "adapters": data["adapters"],
            "namespace": data["namespace"],
            "cluster_id": str(data["cluster_id"]),
            "action": "add",
            "input_tokens": deployment_config["avg_context_length"],
            "output_tokens": deployment_config["avg_sequence_length"],
            "notification_metadata": {
                "name": BUD_INTERNAL_WORKFLOW,
                "subscriber_ids": str(current_user_id),
                "workflow_id": str(db_workflow.id),
            },
            "source_topic": f"{app_settings.source_topic}",
        }
        logger.debug(f"Adapter deployment payload: {payload}")
        # Perform adapter deployment request
        deployment_response = await self._perform_adapter_deployment_request(payload)

        # Add payload dict to response
        for step in deployment_response["steps"]:
            step["payload"] = {}

        deployment_events = {BudServeWorkflowStepEventName.ADAPTER_DEPLOYMENT_EVENTS.value: deployment_response}

        current_step_number = current_step_number + 1
        workflow_current_step = current_step_number

        # Update or create next workflow step
        db_workflow_step = await WorkflowStepService(self.session).create_or_update_next_workflow_step(
            db_workflow.id, current_step_number, deployment_events
        )
        logger.debug(f"Workflow step created with id {db_workflow_step.id}")

        # Update progress in workflow
        deployment_response["progress_type"] = BudServeWorkflowStepEventName.ADAPTER_DEPLOYMENT_EVENTS.value
        await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"progress": deployment_response, "current_step": workflow_current_step}
        )

    async def _perform_adapter_deployment_request(self, payload: Dict) -> None:
        """Perform adapter deployment request."""
        quantize_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_cluster_app_id}/method/deployment/deploy-adapter"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(quantize_endpoint, json=payload) as response:
                    response_data = await response.json()
                    if response.status >= 400 or response_data.get("object") == "error":
                        logger.error(f"Failed to perform adapter deployment request: {response_data}")
                        raise ClientException("Unable to perform adapter deployment")

                    return response_data
        except ClientException as e:
            raise e
        except Exception as e:
            logger.error(f"Failed to perform adapter deployment request: {e}")
            raise ClientException("Unable to perform adapter deployment") from e

    async def get_adapters_by_endpoint(
        self,
        endpoint_id: UUID,
        filters: Dict[str, Any] = {},
        offset: int = 0,
        limit: int = 10,
        order_by: List[Tuple[str, str]] = [],
        search: bool = False,
    ) -> List[AdapterModel]:
        """Get all active adapters for a given endpoint.

        Args:
            endpoint_id (UUID): The ID of the endpoint.
            filters (Dict[str, Any], optional): Filters to apply. Defaults to {}.
            offset (int, optional): The offset for pagination. Defaults to 0.
            limit (int, optional): The limit for pagination. Defaults to 10.
            order_by (List[Tuple[str, str]], optional): The order by conditions. Defaults to [].
            search (bool, optional): Whether to perform a search. Defaults to False.

        Returns:
            List[AdapterModel]: A list of active adapters.
        """
        return await AdapterDataManager(self.session).get_all_active_adapters(
            endpoint_id, offset, limit, filters, order_by, search
        )

    async def add_adapter_from_notification_event(self, payload: NotificationPayload) -> None:
        """Add adapter from notification event."""
        logger.debug("Received event for adding adapter")

        deployment_name = payload.content.result["deployment_name"]

        # Get workflow and steps
        workflow_id = payload.workflow_id
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        # Define the keys required for model extraction
        keys_of_interest = ["endpoint_id", "adapter_name", "adapter_model_id"]

        # from workflow steps extract necessary information
        required_data = {}
        for db_workflow_step in db_workflow_steps:
            for key in keys_of_interest:
                if key in db_workflow_step.data:
                    required_data[key] = db_workflow_step.data[key]

        # Check for adapter with duplicate name
        db_adapter = await AdapterDataManager(self.session).retrieve_by_fields(
            AdapterModel,
            {
                "name": required_data["adapter_name"],
                "endpoint_id": required_data["endpoint_id"],
                "status": AdapterStatusEnum.RUNNING,
            },
            missing_ok=True,
            case_sensitive=False,
        )
        if db_adapter:
            logger.error(f"Unable to create adapter with name {required_data['adapter_name']} as it already exists")
            required_data["adapter_name"] = f"{required_data['adapter_name']}_adapter"

        # Create a new adapter instance with the adapter data
        adapter_create = AdapterModel(
            name=required_data["adapter_name"],
            deployment_name=deployment_name,
            endpoint_id=required_data["endpoint_id"],
            model_id=required_data["adapter_model_id"],
            created_by=db_workflow.created_by,
            status=AdapterStatusEnum.RUNNING,
            status_sync_at=datetime.now(),
        )

        # Insert the adapter into the database
        db_adapter = await AdapterDataManager(self.session).insert_one(adapter_create)

        # Create model_table Redis entry for the adapter using parent endpoint's config
        try:
            # Fetch parent endpoint to get URL, namespace, and other routing config
            db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                EndpointModel, {"id": db_adapter.endpoint_id}
            )

            # Credentials is set to Noe, as adapter is only for HF models
            encrypted_credential_data = None

            # Use model.source for provider type (same pattern as endpoint publication)
            model_provider_type = db_endpoint.model.source.lower() if db_endpoint.model.source else "vllm"

            # Add adapter to proxy cache with its own model_table:{adapter_id} entry
            await self.add_model_to_proxy_cache(
                endpoint_id=db_adapter.id,  # Use adapter's ID as the endpoint_id in cache
                model_name=db_adapter.deployment_name,  # Use parent endpoint's namespace
                model_type=model_provider_type,  # Use parent's provider type
                api_base=db_endpoint.url,  # Use parent's URL for routing
                supported_endpoints=db_endpoint.supported_endpoints,  # Use parent's supported endpoints
                encrypted_credential_data=encrypted_credential_data,  # Pass credentials if available
                include_pricing=False,  # Adapters don't have separate pricing
            )
            logger.debug(f"Added adapter {db_adapter.id} to proxy cache with model_table entry")
        except Exception as e:
            logger.error(f"Failed to add adapter {db_adapter.id} to proxy cache: {e}")
            # Don't fail the workflow if cache update fails

        # Update proxy cache to add the new adapter to api_key mappings
        try:
            await CredentialService(self.session).update_proxy_cache(db_endpoint.project_id)
            await self.update_published_model_cache()
            logger.debug(f"Updated proxy cache for project {db_endpoint.project_id} after adapter creation")
        except (RedisException, Exception) as e:
            logger.error(f"Failed to update proxy cache after adapter creation: {e}")

        # Update workflow step data
        workflow_step_data = {
            "adapter_id": str(db_adapter.id),
            "adapter_name": db_adapter.name,
            "deployment_name": deployment_name,
        }

        current_step_number = db_workflow.current_step + 1

        # Update or create next workflow step
        db_workflow_step = await WorkflowStepService(self.session).create_or_update_next_workflow_step(
            db_workflow.id, current_step_number, workflow_step_data
        )
        logger.debug(f"Workflow step created with id {db_workflow_step.id}")

        db_model = await ModelDataManager(self.session).retrieve_by_fields(
            ModelsModel, {"id": required_data["adapter_model_id"]}
        )
        # Send notification to workflow creator
        model_icon = await ModelServiceUtil(self.session).get_model_icon(db_model)
        notification_request = (
            NotificationBuilder()
            .set_content(
                title=db_adapter.name,
                message="Adapter Added",
                icon=model_icon,
                result=NotificationResult(target_id=db_adapter.id, target_type="endpoint").model_dump(
                    exclude_none=True, exclude_unset=True
                ),
            )
            .set_payload(workflow_id=str(db_workflow.id), type=NotificationTypeEnum.ADAPTER_DEPLOYMENT_SUCCESS.value)
            .set_notification_request(subscriber_ids=[str(db_workflow.created_by)])
            .build()
        )
        await BudNotifyService().send_notification(notification_request)

    async def delete_adapter_workflow(self, current_user_id: UUID, adapter_id: UUID) -> None:
        """Delete an adapter."""
        step_number = 1
        workflow_total_steps = 2
        workflow_id = None

        # Validate adapter id
        db_adapter = await AdapterDataManager(self.session).retrieve_by_fields(
            AdapterModel, {"id": adapter_id}, exclude_fields={"status": AdapterStatusEnum.DELETED}
        )
        if not db_adapter:
            logger.error(f"Adapter {adapter_id} not found")
            raise ClientException("Adapter not found")

        if db_adapter.status == AdapterStatusEnum.DELETING:
            raise ClientException("Adapter is already deleting")

        # Retrieve or create workflow
        workflow_create = WorkflowUtilCreate(
            workflow_type=WorkflowTypeEnum.DELETE_ADAPTER,
            title="Delete Adapter",
            total_steps=workflow_total_steps,
            icon=APP_ICONS["general"]["deployment_mono"],
            tag="Deployment",
        )
        db_workflow = await WorkflowService(self.session).retrieve_or_create_workflow(
            workflow_id, workflow_create, current_user_id
        )

        db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel, {"id": db_adapter.endpoint_id}
        )

        adapters, _ = await self._get_adapters_by_endpoint(
            db_adapter.endpoint_id, db_endpoint.name, db_adapter.name, db_adapter.model.local_path, db_adapter.id
        )
        # Get deployment configuration for token parameters
        deployment_config = db_endpoint.deployment_config

        # Create request payload
        payload = {
            "endpoint_name": db_endpoint.name,
            "ingress_url": db_endpoint.cluster.ingress_url if db_endpoint.cluster else "",
            "adapter_path": db_adapter.model.local_path,
            "adapter_name": db_adapter.deployment_name,
            "adapters": adapters,
            "namespace": db_endpoint.namespace,
            "cluster_id": str(db_endpoint.bud_cluster_id) if db_endpoint.bud_cluster_id else "",
            "adapter_id": str(adapter_id),
            "action": "delete",
            "input_tokens": deployment_config["avg_context_length"],
            "output_tokens": deployment_config["avg_sequence_length"],
            "notification_metadata": {
                "name": BUD_INTERNAL_WORKFLOW,
                "subscriber_ids": str(current_user_id),
                "workflow_id": str(db_workflow.id),
            },
            "source_topic": f"{app_settings.source_topic}",
        }
        try:
            # Perform delete adapter request to bud_cluster app
            bud_cluster_response = await self._perform_adapter_deployment_request(payload)
        except ClientException as e:
            await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"status": WorkflowStatusEnum.FAILED}
            )
            raise e

        # Add payload dict to response
        for step in bud_cluster_response["steps"]:
            step["payload"] = {}

        delete_adapter_workflow_id = bud_cluster_response.get("workflow_id")
        delete_adapter_events = {
            BudServeWorkflowStepEventName.ADAPTER_DELETE_EVENTS.value: bud_cluster_response,
            "delete_adapter_workflow_id": delete_adapter_workflow_id,
            "adapter_id": str(db_adapter.id),
        }

        # Insert step details in db
        await WorkflowStepDataManager(self.session).insert_one(
            WorkflowStepModel(
                workflow_id=db_workflow.id,
                step_number=step_number,
                data=delete_adapter_events,
            )
        )
        logger.debug(f"Created workflow step {step_number} for workflow {db_workflow.id}")

        # Update progress in workflow
        bud_cluster_response["progress_type"] = BudServeWorkflowStepEventName.ADAPTER_DELETE_EVENTS.value
        await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"progress": bud_cluster_response, "current_step": step_number}
        )

        # Update adapter status to deleting
        await AdapterDataManager(self.session).update_by_fields(db_adapter, {"status": AdapterStatusEnum.DELETING})

        return db_workflow

    async def delete_adapter_from_notification_event(self, payload: NotificationPayload) -> None:
        """Delete adapter from notification event."""
        logger.debug("Received event for deleting adapter")

        # Get workflow and steps
        workflow_id = payload.workflow_id
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        # Define the keys required for model extraction
        keys_of_interest = ["adapter_id"]

        # from workflow steps extract necessary information
        required_data = {}
        for db_workflow_step in db_workflow_steps:
            for key in keys_of_interest:
                if key in db_workflow_step.data:
                    required_data[key] = db_workflow_step.data[key]

        db_adapter = await AdapterDataManager(self.session).retrieve_by_fields(
            AdapterModel, {"id": required_data["adapter_id"]}
        )

        # Mark adapter as deleted
        await AdapterDataManager(self.session).update_by_fields(db_adapter, {"status": AdapterStatusEnum.DELETED})
        logger.debug(f"Adapter {db_adapter.id} marked as deleted")

        # Delete the adapter's model_table Redis entry using existing method
        try:
            await self.delete_model_from_proxy_cache(db_adapter.id)
            logger.debug(f"Deleted model_table:{db_adapter.id} from Redis cache")
        except Exception as e:
            logger.error(f"Failed to delete model_table entry for adapter {db_adapter.id}: {e}")

        # Update proxy cache to remove the deleted adapter
        try:
            # Get the endpoint to find the project_id
            db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                EndpointModel, {"id": db_adapter.endpoint_id}
            )
            await CredentialService(self.session).update_proxy_cache(db_endpoint.project_id)
            await self.update_published_model_cache()
            logger.debug(f"Updated proxy cache for project {db_endpoint.project_id} after adapter deletion")
        except (RedisException, Exception) as e:
            logger.error(f"Failed to update proxy cache after adapter deletion: {e}")

        # Mark workflow as completed
        await WorkflowDataManager(self.session).update_by_fields(db_workflow, {"status": WorkflowStatusEnum.COMPLETED})

        # Send notification to workflow creator
        model_icon = await ModelServiceUtil(self.session).get_model_icon(db_adapter.model)
        notification_request = (
            NotificationBuilder()
            .set_content(
                title=db_adapter.name,
                message="Adapter Deleted",
                icon=model_icon,
                result=NotificationResult(target_id=db_adapter.id, target_type="endpoint").model_dump(
                    exclude_none=True, exclude_unset=True
                ),
            )
            .set_payload(workflow_id=str(db_workflow.id), type=NotificationTypeEnum.ADAPTER_DELETION_SUCCESS.value)
            .set_notification_request(subscriber_ids=[str(db_workflow.created_by)])
            .build()
        )
        await BudNotifyService().send_notification(notification_request)

    def _create_provider_config(
        self,
        provider_enum: ProxyProviderEnum,
        model_name: str,
        endpoint_id: UUID,
        api_base: str,
        encrypted_credential_data: Optional[dict] = None,
    ) -> tuple[Any, Optional[str]]:
        """Create provider configuration based on provider type.

        Returns:
            Tuple of (provider_config, encrypted_api_key) where encrypted_api_key is stored for _api_key field
        """
        # Base configuration parameters
        config_params = {"model_name": model_name}
        encrypted_api_key = None

        # Handle API key for providers that use simple api_key field
        if provider_enum in [
            ProxyProviderEnum.OPENAI,
            ProxyProviderEnum.ANTHROPIC,
            ProxyProviderEnum.DEEPSEEK,
            ProxyProviderEnum.FIREWORKS,
            ProxyProviderEnum.GOOGLE_AI_STUDIO,
            ProxyProviderEnum.HYPERBOLIC,
            ProxyProviderEnum.MISTRAL,
            ProxyProviderEnum.TOGETHER,
            ProxyProviderEnum.XAI,
            ProxyProviderEnum.AZURE,
        ]:
            if encrypted_credential_data:
                encrypted_api_key = encrypted_credential_data.get("api_key")
                if encrypted_api_key is not None:
                    config_params["api_key_location"] = f"dynamic::store_{endpoint_id}"

        # Provider-specific configurations
        if provider_enum == ProxyProviderEnum.VLLM:
            return VLLMConfig(model_name=model_name, api_base=api_base + "/v1", api_key_location="none"), None

        elif provider_enum == ProxyProviderEnum.OPENAI:
            if encrypted_credential_data:
                if api_base_val := encrypted_credential_data.get("api_base"):
                    config_params["api_base"] = api_base_val
                if org := encrypted_credential_data.get("organization"):
                    config_params["organization"] = org
            return OpenAIConfig(**config_params), encrypted_api_key

        elif provider_enum == ProxyProviderEnum.ANTHROPIC:
            return AnthropicConfig(**config_params), encrypted_api_key

        elif provider_enum == ProxyProviderEnum.AWS_BEDROCK:
            config_params["model_id"] = model_name
            config_params["region"] = "us-east-1"  # Default
            if encrypted_credential_data:
                if region := encrypted_credential_data.get("aws_region_name"):
                    config_params["region"] = region
                if access_key := encrypted_credential_data.get("aws_access_key_id"):
                    config_params["api_key_location"] = f"dynamic::store_{endpoint_id}"
                    config_params["aws_access_key_id"] = access_key
                    encrypted_api_key = access_key  # Store encrypted key for _api_key field
                if secret_key := encrypted_credential_data.get("aws_secret_access_key"):
                    config_params["aws_secret_access_key"] = secret_key
                if session_token := encrypted_credential_data.get("aws_session_token"):
                    config_params["aws_session_token"] = session_token
            return AWSBedrockConfig(**config_params), encrypted_api_key

        elif provider_enum == ProxyProviderEnum.AWS_SAGEMAKER:
            config_params.update(
                {
                    "endpoint_name": model_name,
                    "region": "us-east-1",
                    "hosted_provider": "openai",
                }
            )
            if encrypted_credential_data:
                if region := encrypted_credential_data.get("aws_region_name"):
                    config_params["region"] = region
                if hosted := encrypted_credential_data.get("hosted_provider"):
                    config_params["hosted_provider"] = hosted
                if access_key := encrypted_credential_data.get("aws_access_key_id"):
                    config_params["api_key_location"] = f"dynamic::store_{endpoint_id}"
                    config_params["aws_access_key_id"] = access_key
                    encrypted_api_key = access_key
                if secret_key := encrypted_credential_data.get("aws_secret_access_key"):
                    config_params["aws_secret_access_key"] = secret_key
                if session_token := encrypted_credential_data.get("aws_session_token"):
                    config_params["aws_session_token"] = session_token
            return AWSSageMakerConfig(**config_params), encrypted_api_key

        elif provider_enum == ProxyProviderEnum.AZURE:
            config_params.update(
                {
                    "deployment_id": model_name,
                    "endpoint": api_base,
                }
            )
            if encrypted_credential_data:
                if api_base_cred := encrypted_credential_data.get("api_base"):
                    config_params["endpoint"] = api_base_cred
                if deployment_id := encrypted_credential_data.get("deployment_id"):
                    config_params["deployment_id"] = deployment_id
                if api_version := encrypted_credential_data.get("api_version"):
                    config_params["api_version"] = api_version
                if azure_ad_token := encrypted_credential_data.get("azure_ad_token"):
                    config_params["azure_ad_token"] = azure_ad_token
                if tenant_id := encrypted_credential_data.get("tenant_id"):
                    config_params["tenant_id"] = tenant_id
                if client_id := encrypted_credential_data.get("client_id"):
                    config_params["client_id"] = client_id
                if client_secret := encrypted_credential_data.get("client_secret"):
                    config_params["client_secret"] = client_secret
            return AzureConfig(**config_params), encrypted_api_key

        elif provider_enum == ProxyProviderEnum.GCP_VERTEX:
            config_params.update(
                {
                    "project_id": "default-project",
                    "region": "us-central1",
                }
            )
            if encrypted_credential_data:
                if vertex_project := encrypted_credential_data.get("vertex_project"):
                    config_params["project_id"] = vertex_project
                elif project_id := encrypted_credential_data.get("project_id"):
                    config_params["project_id"] = project_id
                if vertex_location := encrypted_credential_data.get("vertex_location"):
                    config_params["region"] = vertex_location
                    config_params["vertex_location"] = vertex_location
                if vertex_creds := encrypted_credential_data.get("vertex_credentials"):
                    config_params["api_key_location"] = f"dynamic::store_{endpoint_id}"
                    config_params["vertex_credentials"] = vertex_creds
                    encrypted_api_key = vertex_creds  # Store encrypted key for _api_key field
            return GCPVertexConfig(**config_params), encrypted_api_key

        elif provider_enum == ProxyProviderEnum.DEEPSEEK:
            return DeepSeekConfig(**config_params), encrypted_api_key

        elif provider_enum == ProxyProviderEnum.FIREWORKS:
            return FireworksConfig(**config_params), encrypted_api_key

        elif provider_enum == ProxyProviderEnum.GOOGLE_AI_STUDIO:
            return GoogleAIStudioConfig(**config_params), encrypted_api_key

        elif provider_enum == ProxyProviderEnum.HYPERBOLIC:
            return HyperbolicConfig(**config_params), encrypted_api_key

        elif provider_enum == ProxyProviderEnum.MISTRAL:
            return MistralConfig(**config_params), encrypted_api_key

        elif provider_enum == ProxyProviderEnum.TOGETHER:
            return TogetherConfig(**config_params), encrypted_api_key

        elif provider_enum == ProxyProviderEnum.XAI:
            return XAIConfig(**config_params), encrypted_api_key

        else:
            # Default fallback to VLLM
            return VLLMConfig(model_name=model_name, api_base=api_base + "/v1", api_key_location="none"), None

    # Provider mapping constant
    PROVIDER_MAPPING = {
        "openai": ProxyProviderEnum.OPENAI,
        "anthropic": ProxyProviderEnum.ANTHROPIC,
        "aws-bedrock": ProxyProviderEnum.AWS_BEDROCK,
        "bedrock": ProxyProviderEnum.AWS_BEDROCK,
        "aws-sagemaker": ProxyProviderEnum.AWS_SAGEMAKER,
        "sagemaker": ProxyProviderEnum.AWS_SAGEMAKER,
        "azure": ProxyProviderEnum.AZURE,
        "deepseek": ProxyProviderEnum.DEEPSEEK,
        "fireworks": ProxyProviderEnum.FIREWORKS,
        "gcp-vertex": ProxyProviderEnum.GCP_VERTEX,
        "vertex-ai": ProxyProviderEnum.GCP_VERTEX,
        "google-ai-studio": ProxyProviderEnum.GOOGLE_AI_STUDIO,
        "hyperbolic": ProxyProviderEnum.HYPERBOLIC,
        "mistral": ProxyProviderEnum.MISTRAL,
        "together": ProxyProviderEnum.TOGETHER,
        "xai": ProxyProviderEnum.XAI,
        "vllm": ProxyProviderEnum.VLLM,
    }

    async def add_model_to_proxy_cache(
        self,
        endpoint_id: UUID,
        model_name: str,
        model_type: str,
        api_base: str,
        supported_endpoints: Union[List[str], Dict[str, bool]],
        encrypted_credential_data: Optional[dict] = None,
        include_pricing: bool = True,
    ) -> None:
        """Add model to proxy cache for a project with pricing information.

        Args:
            endpoint_id: The endpoint ID
            model_name: The model name
            model_type: The model type (e.g., "openai", "aws-bedrock", etc.)
            api_base: The base API URL
            supported_endpoints: List of supported endpoints
            encrypted_credential_data: Optional encrypted credential data from ProprietaryCredential.other_provider_creds
            include_pricing: Whether to include pricing information in the cache
        """
        endpoints = []

        for support_endpoint in supported_endpoints:
            # Handle both enum objects and string values
            if isinstance(support_endpoint, ModelEndpointEnum):
                endpoint_value = support_endpoint.value
            else:
                endpoint_value = support_endpoint

            # Use direct mapping for O(1) lookup
            endpoint_name = ENDPOINT_PATH_TO_NAME.get(endpoint_value)
            if endpoint_name:
                endpoints.append(endpoint_name)
            else:
                logger.debug(f"Support endpoint {endpoint_value} is not a valid ModelEndpointEnum")

        logger.debug(f"Converted supported_endpoints to names: {endpoints}")

        # Get the provider enum, default to VLLM if not found
        provider_enum = self.PROVIDER_MAPPING.get(
            model_type.lower() if model_type else model_type, ProxyProviderEnum.VLLM
        )

        # Create the appropriate provider config using helper method
        provider_config, encrypted_model_api_key = self._create_provider_config(
            provider_enum, model_name, endpoint_id, api_base, encrypted_credential_data
        )

        # Initialize providers and routing
        providers = {provider_enum: provider_config}
        routing = [provider_enum]

        # Add BudDoc provider if document endpoint is supported
        if "document" in endpoints:
            buddoc_config = BudDocConfig(
                type="buddoc",
                api_base=app_settings.bud_doc_service_url,
                model_name=model_name,
                api_key_location=app_settings.bud_doc_api_key_location,
            )
            providers[ProxyProviderEnum.BUDDOC] = buddoc_config
            routing.append(ProxyProviderEnum.BUDDOC)

        # Get pricing information if requested
        pricing = None
        if include_pricing:
            pricing_info = await self.get_current_pricing(endpoint_id)
            if pricing_info:
                pricing = ProxyModelPricing(
                    input_cost=float(pricing_info.input_cost),
                    output_cost=float(pricing_info.output_cost),
                    currency=pricing_info.currency,
                    per_tokens=pricing_info.per_tokens,
                )

        # Create the proxy model configuration using the schema
        model_config = ProxyModelConfig(
            routing=routing,
            providers=providers,
            endpoints=endpoints,
            api_key=encrypted_model_api_key,
            pricing=pricing,
        )
        redis_service = RedisService()
        await redis_service.set(
            f"model_table:{endpoint_id}", json.dumps({str(endpoint_id): model_config.model_dump(exclude_none=True)})
        )

    async def update_pricing_in_proxy_cache(self, endpoint_id: UUID) -> None:
        """Update pricing information in the model_table cache.

        Args:
            endpoint_id: The endpoint ID to update pricing for
        """
        try:
            redis_service = RedisService()

            # Get current model_table entry
            cache_key = f"model_table:{endpoint_id}"
            cached_data = await redis_service.get(cache_key)

            if cached_data:
                model_data = json.loads(cached_data)

                # Get current pricing
                pricing_info = await self.get_current_pricing(endpoint_id)

                # Update pricing in the model data
                if str(endpoint_id) in model_data:
                    if pricing_info:
                        # Create pricing object using schema
                        pricing = ProxyModelPricing(
                            input_cost=float(pricing_info.input_cost),
                            output_cost=float(pricing_info.output_cost),
                            currency=pricing_info.currency,
                            per_tokens=pricing_info.per_tokens,
                        )
                        model_data[str(endpoint_id)]["pricing"] = pricing.model_dump()
                    else:
                        # Remove pricing if not available
                        model_data[str(endpoint_id)].pop("pricing", None)

                    # Save back to Redis
                    await redis_service.set(cache_key, json.dumps(model_data))
                    logger.info(f"Updated pricing in model_table for endpoint {endpoint_id}")
            else:
                logger.warning(f"No model_table entry found for endpoint {endpoint_id}")

        except Exception as e:
            logger.error(f"Failed to update pricing in proxy cache: {e}")
            # Don't raise - cache update failure shouldn't block the operation

    async def delete_model_from_proxy_cache(self, endpoint_id: UUID) -> None:
        """Delete model from proxy cache for a project."""
        redis_service = RedisService()
        await redis_service.delete_keys_by_pattern(f"model_table:{endpoint_id}*")

    async def get_deployment_settings(self, endpoint_id: UUID) -> "DeploymentSettingsConfig":
        """Get deployment settings for an endpoint.

        Args:
            endpoint_id: The endpoint ID

        Returns:
            DeploymentSettingsConfig with current settings or defaults

        Raises:
            ClientException: If endpoint not found
        """
        from .schemas import DeploymentSettingsConfig

        # Retrieve endpoint
        endpoint_manager = EndpointDataManager(self.session)
        db_endpoint = await endpoint_manager.retrieve_by_fields(EndpointModel, {"id": endpoint_id})

        if not db_endpoint:
            raise ClientException(
                message=f"Endpoint with id {endpoint_id} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Get deployment_settings from endpoint, default to empty dict
        deployment_settings_data = db_endpoint.deployment_settings or {}

        # Log if we're returning defaults (helps with debugging)
        if not deployment_settings_data:
            logger.info(f"No deployment settings found for endpoint {endpoint_id}, returning defaults")
        else:
            logger.info(f"Found deployment settings for endpoint {endpoint_id}")

        # Create DeploymentSettingsConfig from data
        return DeploymentSettingsConfig(**deployment_settings_data)

    async def update_deployment_settings(
        self,
        endpoint_id: UUID,
        settings: "UpdateDeploymentSettingsRequest",
        current_user_id: UUID,
    ) -> "DeploymentSettingsConfig":
        """Update deployment settings for an endpoint.

        Args:
            endpoint_id: The endpoint ID
            settings: The new deployment settings
            current_user_id: The ID of the current user

        Returns:
            Updated DeploymentSettingsConfig

        Raises:
            ClientException: If endpoint not found or validation fails
        """
        from .schemas import DeploymentSettingsConfig

        # Retrieve endpoint
        endpoint_manager = EndpointDataManager(self.session)
        db_endpoint = await endpoint_manager.retrieve_by_fields(EndpointModel, {"id": endpoint_id})

        if not db_endpoint:
            raise ClientException(
                message=f"Endpoint with id {endpoint_id} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Get existing deployment settings
        existing_settings_data = db_endpoint.deployment_settings or {}
        existing_settings = DeploymentSettingsConfig(**existing_settings_data)

        # Merge settings - only update provided fields
        update_data = settings.model_dump(exclude_none=True)

        # Create merged settings
        merged_settings_data = existing_settings.model_dump()
        for key, value in update_data.items():
            if value is not None:
                merged_settings_data[key] = value

        # Create new settings object to validate
        new_settings = DeploymentSettingsConfig(**merged_settings_data)

        # Validate deployment settings
        await self._validate_deployment_settings(new_settings, db_endpoint)

        logger.info(f"Updated deployment settings for endpoint {endpoint_id}")

        # Update endpoint with new deployment settings
        await endpoint_manager.update_by_fields(
            db_endpoint,
            {"deployment_settings": new_settings.model_dump()},
        )

        # Ensure the changes are immediately available for subsequent reads
        self.session.flush()

        # Publish to cache for gateway
        await self._publish_deployment_settings_to_cache(db_endpoint, new_settings)

        # Send notification about settings update
        notification_request = (
            NotificationBuilder()
            .set_content(
                title="Deployment Settings Updated",
                message=f"Deployment settings for endpoint {db_endpoint.name} have been updated",
                icon=APP_ICONS["general"]["deployment_mono"],
                result=NotificationResult(target_id=db_endpoint.id, target_type="endpoint").model_dump(
                    exclude_none=True, exclude_unset=True
                ),
            )
            .set_payload(
                workflow_id=str(uuid4()),  # Generate a unique ID for this notification
                type=NotificationTypeEnum.DEPLOYMENT_SUCCESS.value,
            )
            .set_notification_request(subscriber_ids=[str(current_user_id)])
            .build()
        )
        await BudNotifyService().send_notification(notification_request)

        return new_settings

    async def _validate_deployment_settings(
        self,
        settings: "DeploymentSettingsConfig",
        endpoint: EndpointModel,
    ) -> None:
        """Validate deployment settings.

        Args:
            settings: The deployment settings to validate
            endpoint: The endpoint model

        Raises:
            ClientException: If validation fails
        """
        # Validate fallback endpoints if provided
        if settings.fallback_config and settings.fallback_config.fallback_models:
            endpoint_manager = EndpointDataManager(self.session)

            for fallback_endpoint_id in settings.fallback_config.fallback_models:
                try:
                    # Parse as UUID
                    fallback_uuid = UUID(fallback_endpoint_id)
                except ValueError:
                    raise ClientException(
                        message=f"Invalid fallback endpoint ID: '{fallback_endpoint_id}' (must be a valid UUID)",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

                # Validate endpoint exists in the same project
                fallback_endpoint = await endpoint_manager.retrieve_by_fields(
                    EndpointModel, {"id": fallback_uuid, "project_id": endpoint.project_id}, missing_ok=True
                )

                if not fallback_endpoint:
                    raise ClientException(
                        message=f"Fallback endpoint '{fallback_endpoint_id}' not found in project",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

                # Ensure fallback endpoint is not the same as current endpoint
                if str(fallback_uuid) == str(endpoint.id):
                    raise ClientException(
                        message="Fallback endpoint cannot be the same as current endpoint",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

                # Ensure fallback endpoint is running
                if fallback_endpoint.status != EndpointStatusEnum.RUNNING:
                    raise ClientException(
                        message=f"Fallback endpoint '{fallback_endpoint_id}' is not in RUNNING state",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

    async def _publish_deployment_settings_to_cache(
        self,
        endpoint: EndpointModel,
        settings: "DeploymentSettingsConfig",
    ) -> None:
        """Publish deployment settings to cache in gateway format.

        Args:
            endpoint: The endpoint model
            settings: The deployment settings
        """
        try:
            # Get model information
            model_manager = ModelDataManager(self.session)
            model = await model_manager.retrieve_by_fields(ModelsModel, {"id": endpoint.model_id})

            if not model:
                logger.warning(f"Model not found for endpoint {endpoint.id}")
                return

            # Get existing cache data if any
            redis_service = RedisService()
            cache_key = f"model_table:{endpoint.id}"
            existing_data = await redis_service.get(cache_key)

            if existing_data:
                model_data = json.loads(existing_data)
                endpoint_data = model_data.get(str(endpoint.id), {})
            else:
                # If no existing data, we need to construct basic model data
                endpoint_data = {
                    "routing": [],
                    "endpoints": [ep.value for ep in endpoint.supported_endpoints],
                    "providers": {},
                }

            # Add deployment settings to the model data
            if settings.fallback_config:
                if settings.fallback_config.fallback_models:
                    endpoint_data["fallback_models"] = settings.fallback_config.fallback_models
                else:
                    # Explicitly remove fallback_models if the list is empty
                    endpoint_data.pop("fallback_models", None)

            if settings.retry_config:
                endpoint_data["retry_config"] = {
                    "num_retries": settings.retry_config.num_retries,
                    "max_delay_s": settings.retry_config.max_delay_s,
                }

            if settings.rate_limits:
                endpoint_data["rate_limits"] = {
                    "algorithm": settings.rate_limits.algorithm,
                    "requests_per_second": settings.rate_limits.requests_per_second,
                    "requests_per_minute": settings.rate_limits.requests_per_minute,
                    "requests_per_hour": settings.rate_limits.requests_per_hour,
                    "burst_size": settings.rate_limits.burst_size,
                    "enabled": settings.rate_limits.enabled,
                    "cache_ttl_ms": 200,
                    "local_allowance": 0.8,
                    "sync_interval_ms": 100,
                }

            # Update cache
            await redis_service.set(
                cache_key,
                json.dumps({str(endpoint.id): endpoint_data}),
            )

            logger.info(f"Published deployment settings to cache for endpoint {endpoint.id}")

        except Exception as e:
            logger.error(f"Failed to publish deployment settings to cache: {e}")
            # Don't raise exception - cache update failure shouldn't block settings update

    async def update_publication_status(
        self,
        endpoint_id: UUID,
        action: str,
        current_user_id: UUID,
        action_metadata: Optional[dict] = None,
        pricing: Optional[dict] = None,
    ) -> EndpointModel:
        """Update the publication status of an endpoint (publish/unpublish).

        Args:
            endpoint_id (UUID): The ID of the endpoint.
            action (str): The action to perform ("publish" or "unpublish").
            current_user_id (UUID): The ID of the user performing the action.
            action_metadata (Optional[dict]): Additional metadata about the action.
            pricing (Optional[dict]): Pricing information (required when action="publish").

        Returns:
            EndpointModel: The updated endpoint.

        Raises:
            ClientException: If endpoint not found, invalid action, or missing pricing when publishing.
        """
        # Retrieve the endpoint
        endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel,
            {"id": endpoint_id},
            exclude_fields={"status": EndpointStatusEnum.DELETED},
            missing_ok=True,
        )

        if not endpoint:
            raise ClientException(
                status_code=status.HTTP_404_NOT_FOUND,
                message=f"Endpoint with ID {endpoint_id} not found",
            )

        # Validate action
        if action not in ["publish", "unpublish"]:
            raise ClientException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Invalid action: {action}. Must be 'publish' or 'unpublish'.",
            )

        # Check current state
        if action == "publish" and endpoint.is_published:
            # Idempotent - return success without error
            logger.info(f"Endpoint {endpoint_id} is already published")
            return endpoint

        if action == "unpublish" and not endpoint.is_published:
            # Idempotent - return success without error
            logger.info(f"Endpoint {endpoint_id} is already unpublished")
            return endpoint

        # For publish action, check if endpoint is in valid state
        if action == "publish" and endpoint.status != EndpointStatusEnum.RUNNING:
            raise ClientException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Cannot publish endpoint in {endpoint.status} state. Endpoint must be in RUNNING state to be published.",
            )

        # Validate pricing is provided when publishing
        if action == "publish" and not pricing:
            raise ClientException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Pricing information is required when publishing an endpoint.",
            )

        # Capture previous state for history
        previous_state = {
            "is_published": endpoint.is_published,
            "published_date": endpoint.published_date.isoformat() if endpoint.published_date else None,
            "published_by": str(endpoint.published_by) if endpoint.published_by else None,
        }

        # Update publication status
        action_time = datetime.now(timezone.utc)
        is_published = action == "publish"
        published_date = action_time if is_published else None

        # Handle pricing for publish action
        if is_published and pricing:
            # Validate pricing values before database operation
            input_cost = float(pricing.get("input_cost", 0))
            output_cost = float(pricing.get("output_cost", 0))

            if input_cost >= 10000 or output_cost >= 10000:
                raise ClientException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message=f"Pricing values must be less than 10000. Got input_cost: {input_cost}, output_cost: {output_cost}",
                )

            # Begin transaction to ensure atomicity
            try:
                # Update previous pricing records to not current
                await EndpointDataManager(self.session).update_previous_pricing(endpoint_id)

                # Create new pricing record
                await EndpointDataManager(self.session).create_deployment_pricing(
                    endpoint_id=endpoint_id,
                    pricing_data=pricing,
                    created_by=current_user_id,
                )
            except Exception as e:
                logger.error(f"Failed to create pricing for endpoint {endpoint_id}: {e}")
                self.session.rollback()
                raise ClientException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Failed to create pricing for endpoint",
                )

        endpoint = await EndpointDataManager(self.session).update_publication_status(
            endpoint_id=endpoint_id,
            is_published=is_published,
            published_by=current_user_id,
            published_date=published_date,
        )

        # Capture new state for history
        new_state = {
            "is_published": endpoint.is_published,
            "published_date": endpoint.published_date.isoformat() if endpoint.published_date else None,
            "published_by": str(endpoint.published_by) if endpoint.published_by else None,
        }

        # Create publication history entry
        await PublicationHistoryDataManager(self.session).create_publication_history(
            deployment_id=endpoint_id,
            action=action,
            performed_by=current_user_id,
            performed_at=action_time,
            action_metadata=action_metadata,
            previous_state=previous_state,
            new_state=new_state,
        )

        # Invalidate catalog cache when publication status changes
        redis_service = RedisService()
        await redis_service.invalidate_catalog_cache(endpoint_id=str(endpoint_id))

        logger.info(f"Endpoint {endpoint_id} {action}ed successfully by user {current_user_id}")

        # Update model_table cache for budgateway based on publication status
        try:
            if is_published:
                # Add/update model in cache when publishing
                await self._update_model_table_cache_for_endpoint(endpoint)
                logger.info(f"Updated model_table cache for published endpoint {endpoint_id}")
        except Exception as e:
            logger.error(f"Failed to update model_table cache for endpoint {endpoint_id}: {e}")
            # Don't fail the main operation if cache update fails

        # Update published model info cache
        await self.update_published_model_cache()

        return endpoint

    async def update_published_model_cache(self) -> None:
        """Update the cache with all published model information.

        This method collects all published endpoints across all projects and updates
        the Redis cache with a mapping of model names to their endpoint metadata.

        Cache format:
        {
            <model_name>: {
                "endpoint_id": <endpoint_id>,
                "model_id": <model_id>,
                "project_id": <project_id>
            }
        }
        """
        try:
            # Get all published endpoints
            published_endpoints = await EndpointDataManager(self.session).get_all_published_endpoints()

            # Build the cache data structure
            published_models = {}
            for endpoint in published_endpoints:
                # Use endpoint name as the key (model name)
                published_models[endpoint.name] = {
                    "endpoint_id": str(endpoint.id),
                    "model_id": str(endpoint.model_id),
                    "project_id": str(endpoint.project_id),
                }

            # Update the cache
            redis_service = RedisService()
            await redis_service.set(name="published_model_info", value=json.dumps(published_models))

            logger.info(f"Updated published model cache with {len(published_models)} endpoints")
        except Exception as e:
            logger.error(f"Failed to update published model cache: {e}")
            # Don't raise exception - cache update failure shouldn't block the main operation

    async def _update_model_table_cache_for_endpoint(self, endpoint: EndpointModel) -> None:
        """Update the model_table cache for a specific endpoint.

        This method updates the budgateway model_table cache with endpoint and pricing information.

        Args:
            endpoint: The endpoint model to update cache for
        """
        # Get model information
        if not endpoint.model:
            # If model relationship isn't loaded, load it
            endpoint_with_model = await EndpointDataManager(self.session).retrieve_by_fields(
                EndpointModel,
                {"id": endpoint.id},
                exclude_fields={"status": EndpointStatusEnum.DELETED},
                missing_ok=True,
                include_relationships=["model", "credential"],
            )
            if not endpoint_with_model:
                raise Exception(f"Endpoint {endpoint.id} not found")
            endpoint = endpoint_with_model

        # Get credential data if available
        encrypted_credential_data = None
        if endpoint.credential and hasattr(endpoint.credential, "other_provider_creds"):
            encrypted_credential_data = endpoint.credential.other_provider_creds

        # Merge endpoint's supported_endpoints with model's capabilities
        # Ensure we only work with string values, not enum objects
        merged_endpoints = set()

        # Add endpoint's existing supported endpoints (convert to values if enum objects)
        if endpoint.supported_endpoints:
            for ep in endpoint.supported_endpoints:
                if isinstance(ep, ModelEndpointEnum):
                    merged_endpoints.add(ep.value)
                else:
                    merged_endpoints.add(ep)
            logger.debug(f"Endpoint {endpoint.id} has supported_endpoints: {endpoint.supported_endpoints}")

        # Add model capabilities (convert to values if enum objects)
        if endpoint.model and endpoint.model.supported_endpoints:
            logger.debug(f"Model {endpoint.model.name} has supported_endpoints: {endpoint.model.supported_endpoints}")
            for model_ep in endpoint.model.supported_endpoints:
                if isinstance(model_ep, ModelEndpointEnum):
                    merged_endpoints.add(model_ep.value)
                    if model_ep == ModelEndpointEnum.DOCUMENT:
                        logger.info(f"Added document endpoint support for model {endpoint.model.name} when publishing")
                else:
                    merged_endpoints.add(model_ep)
                    if model_ep == ModelEndpointEnum.DOCUMENT.value:
                        logger.info(f"Added document endpoint support for model {endpoint.model.name} when publishing")

        final_endpoints = list(merged_endpoints)
        logger.info(f"Final supported endpoints for publishing: {final_endpoints}")

        # Call add_model_to_proxy_cache with endpoint information
        # Use model.source for provider type (openai, anthropic, etc.), not model_type (which is architecture info)
        model_provider_type = endpoint.model.source.lower() if endpoint.model.source else "vllm"
        await self.add_model_to_proxy_cache(
            endpoint_id=endpoint.id,
            model_name=endpoint.namespace,
            model_type=model_provider_type,  # Use source field for provider type
            api_base=endpoint.url,
            supported_endpoints=final_endpoints,  # Use merged endpoints
            encrypted_credential_data=encrypted_credential_data,
            include_pricing=True,  # Always include pricing when publishing
        )

    async def _remove_from_model_table_cache(self, endpoint_id: UUID) -> None:
        """Remove an endpoint from the model_table cache.

        Args:
            endpoint_id: The endpoint ID to remove from cache
        """
        redis_service = RedisService()
        cache_key = f"model_table:{endpoint_id}"
        await redis_service.delete(cache_key)

    async def get_current_pricing(self, endpoint_id: UUID) -> Optional["DeploymentPricing"]:
        """Get the current pricing for an endpoint.

        Args:
            endpoint_id (UUID): The ID of the endpoint.

        Returns:
            Optional[DeploymentPricing]: The current pricing record, or None if not found.
        """
        return await EndpointDataManager(self.session).get_current_pricing(endpoint_id)

    async def update_pricing(
        self, endpoint_id: UUID, pricing_data: Dict[str, Any], current_user_id: UUID
    ) -> DeploymentPricing:
        """Update pricing for a published endpoint.

        Args:
            endpoint_id (UUID): The ID of the endpoint.
            pricing_data (Dict[str, Any]): New pricing information.
            current_user_id (UUID): The ID of the user updating pricing.

        Returns:
            DeploymentPricing: The new pricing record.

        Raises:
            ClientException: If endpoint not found or not published.
        """
        # Verify endpoint exists and is published
        endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel,
            {"id": endpoint_id},
            exclude_fields={"status": EndpointStatusEnum.DELETED},
            missing_ok=True,
        )
        if not endpoint:
            raise ClientException(
                status_code=status.HTTP_404_NOT_FOUND,
                message=f"Endpoint with ID {endpoint_id} not found",
            )

        if not endpoint.is_published:
            raise ClientException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Cannot update pricing for unpublished endpoint",
            )

        try:
            # Begin transaction
            # Deactivate current pricing
            await EndpointDataManager(self.session).update_previous_pricing(endpoint_id)

            # Create new pricing record
            new_pricing = await EndpointDataManager(self.session).create_deployment_pricing(
                endpoint_id=endpoint_id,
                pricing_data=pricing_data,
                created_by=current_user_id,
            )

            # Invalidate catalog cache when pricing changes
            redis_service = RedisService()
            await redis_service.invalidate_catalog_cache(endpoint_id=str(endpoint_id))

            # Update pricing in model_table cache
            await self.update_pricing_in_proxy_cache(endpoint_id)

            logger.info(f"Pricing updated for endpoint {endpoint_id} by user {current_user_id}")
            return new_pricing

        except Exception as e:
            logger.error(f"Failed to update pricing for endpoint {endpoint_id}: {e}")
            self.session.rollback()
            raise ClientException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Failed to update pricing",
            )

    async def get_pricing_history(self, endpoint_id: UUID, page: int = 1, limit: int = 20) -> dict:
        """Get pricing history for an endpoint.

        Args:
            endpoint_id (UUID): The ID of the endpoint.
            page (int): Page number for pagination.
            limit (int): Number of items per page.

        Returns:
            dict: Dictionary containing pricing history and pagination info.

        Raises:
            ClientException: If endpoint not found.
        """
        # Verify endpoint exists
        endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel,
            {"id": endpoint_id},
            exclude_fields={"status": EndpointStatusEnum.DELETED},
            missing_ok=True,
        )
        if not endpoint:
            raise ClientException(
                status_code=status.HTTP_404_NOT_FOUND,
                message=f"Endpoint with ID {endpoint_id} not found",
            )

        # Get pricing history
        offset = (page - 1) * limit
        pricing_history, total_count = await EndpointDataManager(self.session).get_pricing_history(
            endpoint_id=endpoint_id,
            offset=offset,
            limit=limit,
        )

        return {
            "pricing_history": [DeploymentPricingResponse.model_validate(p) for p in pricing_history],
            "page": page,
            "limit": limit,
            "total_record": total_count,
            "code": status.HTTP_200_OK,
        }

    async def get_publication_history(self, endpoint_id: UUID, page: int = 1, limit: int = 20) -> dict:
        """Get publication history for an endpoint.

        Args:
            endpoint_id (UUID): The ID of the endpoint.
            page (int): Page number for pagination.
            limit (int): Number of items per page.

        Returns:
            dict: Dictionary containing history entries and pagination info.

        Raises:
            ClientException: If endpoint not found.
        """
        # Verify endpoint exists
        endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel,
            {"id": endpoint_id},
            missing_ok=True,
        )

        if not endpoint:
            raise ClientException(
                status_code=status.HTTP_404_NOT_FOUND,
                message=f"Endpoint with ID {endpoint_id} not found",
            )

        # Calculate offset
        offset = (page - 1) * limit

        # Get publication history
        history_entries, total_count = await PublicationHistoryDataManager(self.session).get_publication_history(
            deployment_id=endpoint_id,
            offset=offset,
            limit=limit,
        )

        # Transform history entries to include user summary
        transformed_entries = []
        for entry in history_entries:
            entry_dict = {
                "id": entry.id,
                "deployment_id": entry.deployment_id,
                "action": entry.action,
                "performed_by": entry.performed_by,
                "performed_at": entry.performed_at,
                "action_metadata": entry.action_metadata,
                "previous_state": entry.previous_state,
                "new_state": entry.new_state,
                "created_at": entry.created_at,
                "modified_at": entry.modified_at,
            }

            # Add user summary if user details are loaded
            if entry.performed_by_user:
                entry_dict["performed_by_user"] = {
                    "id": entry.performed_by_user.id,
                    "email": entry.performed_by_user.email,
                    "name": entry.performed_by_user.name,
                }
            else:
                entry_dict["performed_by_user"] = None

            transformed_entries.append(entry_dict)

        return {
            "history": transformed_entries,
            "total_record": total_count,
            "page": page,
            "limit": limit,
            "code": status.HTTP_200_OK,
            "message": "Successfully retrieved publication history",
        }
