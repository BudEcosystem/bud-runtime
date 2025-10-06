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

"""Business logic services for the prompt ops module."""

import json
from ast import Dict
from typing import Any, Dict, Optional
from uuid import UUID

import aiohttp
from fastapi import status

from ..commons import logging
from ..commons.config import app_settings
from ..commons.constants import (
    APP_ICONS,
    BUD_INTERNAL_WORKFLOW,
    BUD_PROMPT_API_KEY_LOCATION,
    BudServeWorkflowStepEventName,
    EndpointStatusEnum,
    ModelEndpointEnum,
    ModelProviderTypeEnum,
    ProjectStatusEnum,
    PromptStatusEnum,
    PromptTypeEnum,
    PromptVersionStatusEnum,
    ProxyProviderEnum,
    VisibilityEnum,
    WorkflowStatusEnum,
    WorkflowTypeEnum,
)
from ..commons.db_utils import SessionMixin
from ..commons.exceptions import ClientException
from ..core.schemas import NotificationPayload
from ..credential_ops.services import CredentialService
from ..endpoint_ops.crud import EndpointDataManager
from ..endpoint_ops.models import Endpoint as EndpointModel
from ..endpoint_ops.schemas import ProxyModelConfig, ProxyModelPricing
from ..model_ops.crud import ProviderDataManager
from ..model_ops.models import Provider as ProviderModel
from ..project_ops.crud import ProjectDataManager
from ..project_ops.models import Project as ProjectModel
from ..shared.redis_service import RedisService
from ..workflow_ops.crud import WorkflowDataManager, WorkflowStepDataManager
from ..workflow_ops.models import Workflow as WorkflowModel
from ..workflow_ops.schemas import WorkflowUtilCreate
from ..workflow_ops.services import WorkflowService, WorkflowStepService
from .crud import PromptDataManager, PromptVersionDataManager
from .models import Prompt as PromptModel
from .models import PromptVersion as PromptVersionModel
from .schemas import (
    BudPromptConfig,
    CreatePromptWorkflowRequest,
    CreatePromptWorkflowSteps,
    PromptConfigCopyRequest,
    PromptConfigGetResponse,
    PromptConfigRequest,
    PromptConfigResponse,
    PromptConfigurationData,
    PromptFilter,
    PromptListItem,
    PromptResponse,
    PromptSchemaConfig,
    PromptSchemaRequest,
    PromptSchemaWorkflowSteps,
    PromptVersionListItem,
    PromptVersionResponse,
)


logger = logging.get_logger(__name__)


class PromptService(SessionMixin):
    """Service for managing prompts."""

    async def get_all_prompts(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: dict = {},
        order_by: list = [],
        search: bool = False,
    ) -> tuple[list[PromptModel], int]:
        """Get all active prompts with their related data."""
        # Fetch active prompts
        filters["status"] = PromptStatusEnum.ACTIVE

        # Fetch prompts with related data
        db_prompts, count = await PromptDataManager(self.session).get_all_active_prompts(
            offset, limit, filters, order_by, search
        )

        # Transform to response format
        prompts_list = []
        for prompt in db_prompts:
            # Access endpoint and model through default_version
            default_version_obj = prompt.default_version
            endpoint = default_version_obj.endpoint if default_version_obj else None
            model = default_version_obj.model if default_version_obj else None

            # Determine the model icon based on provider type
            model_icon = None
            if model:
                if (
                    model.provider_type in [ModelProviderTypeEnum.HUGGING_FACE, ModelProviderTypeEnum.CLOUD_MODEL]
                    and model.provider_id
                    and model.provider
                ):
                    # Use provider icon for cloud and HF models
                    model_icon = model.provider.icon
                else:
                    # Use model's own icon
                    model_icon = model.icon

            prompt_item = PromptListItem(
                id=prompt.id,
                name=prompt.name,
                description=prompt.description,
                tags=prompt.tags,
                created_at=prompt.created_at,
                modified_at=prompt.modified_at,
                prompt_type=prompt.prompt_type,
                model_icon=model_icon,
                model_name=model.name if model else "",
                default_version=default_version_obj.version if default_version_obj else None,
                modality=model.modality if model else None,
                status=endpoint.status if endpoint else "",
            )
            prompts_list.append(prompt_item)

        return prompts_list, count

    async def get_all_prompt_versions(
        self,
        prompt_id: UUID,
        offset: int = 0,
        limit: int = 10,
        filters: dict = {},
        order_by: list = [],
        search: bool = False,
    ) -> tuple[list[PromptVersionListItem], int]:
        """Get all versions for a specific prompt with their related data."""
        # First validate that the prompt exists and is active
        db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
            PromptModel,
            fields={"id": prompt_id, "status": PromptStatusEnum.ACTIVE},
        )

        if not db_prompt:
            raise ClientException(message="Prompt not found", status_code=status.HTTP_404_NOT_FOUND)

        # Fetch prompt versions with related data and computed is_default_version
        rows, count = await PromptVersionDataManager(self.session).get_all_prompt_versions(
            prompt_id, offset, limit, filters, order_by, search
        )

        # Transform to response format
        versions_list = []
        for row in rows:
            # Extract the model and computed field from the row
            prompt_version = row[0]  # PromptVersionModel
            is_default_version = row[1]  # Computed is_default_version from database

            # Access endpoint name through relationship
            endpoint_name = prompt_version.endpoint.name if prompt_version.endpoint else ""

            version_item = PromptVersionListItem(
                id=prompt_version.id,
                endpoint_name=endpoint_name,
                version=prompt_version.version,
                created_at=prompt_version.created_at,
                modified_at=prompt_version.modified_at,
                is_default_version=is_default_version,
            )
            versions_list.append(version_item)

        return versions_list, count

    async def delete_active_prompt(self, prompt_id: UUID) -> PromptModel:
        """Delete an active prompt by updating its status to DELETED."""
        # Retrieve and validate prompt
        db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
            PromptModel, fields={"id": prompt_id, "status": PromptStatusEnum.ACTIVE}
        )

        # Delete Redis configuration BEFORE updating database
        try:
            prompt_service = PromptService(self.session)
            await prompt_service._perform_delete_prompt_config_request(
                prompt_id=db_prompt.name  # Redis uses prompt name as ID, delete all versions
            )
            logger.debug(f"Deleted all Redis configurations for prompt {db_prompt.name}")
        except ClientException as e:
            if e.status_code == 404:
                # Redis config might not exist, which is okay
                logger.warning(f"Redis configuration not found for prompt {db_prompt.name}: {str(e)}")
            else:
                # Re-raise other errors
                logger.error(f"Failed to delete Redis configuration for prompt {db_prompt.name}: {str(e)}")
                raise

        # Delete from proxy cache
        try:
            await self.delete_prompt_from_proxy_cache(prompt_id)
            logger.debug(f"Deleted prompt {db_prompt.name} from proxy cache")
        except Exception as e:
            logger.error(f"Failed to delete prompt from proxy cache: {e}")
            # Continue - cache cleanup is non-critical

        # Update credential proxy cache to remove deleted prompt
        try:
            credential_service = CredentialService(self.session)
            await credential_service.update_proxy_cache(db_prompt.project_id)
            logger.debug(f"Updated credential proxy cache for project {db_prompt.project_id}")
        except Exception as e:
            logger.error(f"Failed to update credential proxy cache: {e}")
            # Continue - cache cleanup is non-critical

        # Update prompt status to DELETED
        await PromptDataManager(self.session).update_by_fields(db_prompt, {"status": PromptStatusEnum.DELETED})

        # Soft delete all associated prompt versions
        deleted_count = await PromptVersionDataManager(self.session).soft_delete_by_prompt_id(prompt_id)
        logger.debug(f"Soft deleted {deleted_count} prompt versions for prompt {prompt_id}")

        return db_prompt

    async def edit_prompt(self, prompt_id: UUID, data: dict[str, Any]) -> PromptModel:
        """Edit prompt by validating and updating specific fields."""
        # Retrieve existing prompt
        db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
            PromptModel, fields={"id": prompt_id, "status": PromptStatusEnum.ACTIVE}
        )

        # Validate name uniqueness if name is provided
        if "name" in data:
            duplicate_prompt = await PromptDataManager(self.session).retrieve_by_fields(
                PromptModel,
                fields={"name": data["name"]},
                exclude_fields={"id": prompt_id, "status": PromptStatusEnum.DELETED},
                missing_ok=True,
                case_sensitive=False,
            )
            if duplicate_prompt:
                raise ClientException(message="Prompt name already exists", status_code=status.HTTP_400_BAD_REQUEST)

        # Validate default_version_id if provided
        if "default_version_id" in data and data["default_version_id"]:
            # Check if the version exists and belongs to this prompt
            db_version = await PromptVersionDataManager(self.session).retrieve_by_fields(
                PromptVersionModel,
                fields={
                    "id": data["default_version_id"],
                    "prompt_id": prompt_id,
                },
                exclude_fields={"status": PromptVersionStatusEnum.DELETED},
                missing_ok=True,
            )
            if not db_version:
                raise ClientException(
                    message="Invalid default version. Version does not exist or does not belong to this prompt.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Update Redis with new default version BEFORE updating database
            try:
                prompt_service = PromptService(self.session)
                await prompt_service._perform_set_default_version_request(
                    prompt_id=db_prompt.name,  # Redis uses prompt name as ID
                    version=db_version.version,  # Use the version number
                )
                logger.debug(
                    f"Updated Redis default version for prompt {db_prompt.name} to version {db_version.version}"
                )
            except Exception as e:
                logger.error(f"Failed to update Redis default version: {str(e)}")
                raise ClientException(
                    message="Failed to update default version in configuration service",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # Update the prompt
        db_prompt = await PromptDataManager(self.session).update_by_fields(db_prompt, data)

        # Convert to response model
        prompt_response = PromptResponse.model_validate(db_prompt)

        return prompt_response

    async def save_prompt_config(self, request: PromptConfigRequest) -> PromptConfigResponse:
        """Save prompt configuration by forwarding request to budprompt service.

        Args:
            request: The prompt configuration request

        Returns:
            PromptConfigResponse containing the bud_prompt_id and bud_prompt_version
        """
        # Perform the request to budprompt service
        response_data = await self._perform_prompt_config_request(request)

        # Extract prompt_id and version from the response
        prompt_id = response_data.get("prompt_id")
        version = response_data.get("version")

        # Create and return response
        return PromptConfigResponse(
            bud_prompt_id=prompt_id,
            bud_prompt_version=version,
            message="Prompt configuration saved successfully",
            code=status.HTTP_200_OK,
        )

    async def _perform_prompt_config_request(self, request: PromptConfigRequest) -> Dict[str, Any]:
        """Perform prompt configuration request to budprompt service.

        Args:
            request: The prompt configuration request

        Returns:
            Response data from budprompt service
        """
        prompt_config_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_prompt_app_id}/method/v1/prompt/prompt-config"
        )

        # Convert request to dict, excluding None values
        payload = request.model_dump(exclude_none=True)

        logger.debug(f"Performing prompt config request to budprompt: {payload}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(prompt_config_endpoint, json=payload) as response:
                    response_data = await response.json()

                    if response.status != 200:
                        logger.error(f"Failed to save prompt config: {response.status} {response_data}")
                        raise ClientException(
                            message=response_data.get("message", "Failed to save prompt configuration"),
                            status_code=response.status,
                        )

                    logger.debug(f"Successfully saved prompt config: {response_data}")
                    return response_data

        except aiohttp.ClientError as e:
            logger.exception(f"Network error during prompt config request: {e}")
            raise ClientException(
                message="Network error while saving prompt configuration",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from e
        except Exception as e:
            logger.exception(f"Failed to send prompt config request: {e}")
            raise ClientException(
                message="Failed to save prompt configuration", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def get_prompt_config(self, prompt_id: str, version: Optional[int] = None) -> PromptConfigGetResponse:
        """Get prompt configuration from budprompt service.

        Args:
            prompt_id: The prompt configuration identifier
            version: Optional version number to retrieve

        Returns:
            PromptConfigGetResponse containing the configuration data
        """
        # Perform the request to budprompt service
        response_data = await self._perform_get_prompt_config_request(prompt_id, version)

        # Parse the configuration data
        config_data = PromptConfigurationData(**response_data.get("data", {}))

        # Create and return response
        return PromptConfigGetResponse(
            prompt_id=response_data.get("prompt_id"),
            data=config_data,
            message="Prompt configuration retrieved successfully",
            code=status.HTTP_200_OK,
        )

    async def _perform_get_prompt_config_request(
        self, prompt_id: str, version: Optional[int] = None
    ) -> Dict[str, Any]:
        """Perform get prompt configuration request to budprompt service.

        Args:
            prompt_id: The prompt configuration identifier
            version: Optional version number

        Returns:
            Response data from budprompt service
        """
        # Build the URL with optional version query parameter
        prompt_config_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_prompt_app_id}/method/v1/prompt/prompt-config/{prompt_id}"

        # Add version as query parameter if provided
        params = {}
        if version is not None:
            params["version"] = version

        logger.debug(f"Retrieving prompt config from budprompt: prompt_id={prompt_id}, version={version}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(prompt_config_endpoint, params=params) as response:
                    response_data = await response.json()

                    if response.status == 404:
                        raise ClientException(
                            message="Prompt configuration not found", status_code=status.HTTP_404_NOT_FOUND
                        )
                    elif response.status != 200:
                        logger.error(f"Failed to get prompt config: {response.status} {response_data}")
                        raise ClientException(
                            message=response_data.get("message", "Failed to retrieve prompt configuration"),
                            status_code=response.status,
                        )

                    logger.debug(f"Successfully retrieved prompt config: {prompt_id}")
                    return response_data

        except aiohttp.ClientError as e:
            logger.exception(f"Network error during get prompt config request: {e}")
            raise ClientException(
                message="Network error while retrieving prompt configuration",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from e
        except ClientException:
            raise  # Re-raise ClientException as-is
        except Exception as e:
            logger.exception(f"Failed to get prompt config: {e}")
            raise ClientException(
                message="Failed to retrieve prompt configuration", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def _copy_prompt_config(self, request: PromptConfigCopyRequest) -> Dict[str, Any]:
        """Copy prompt configuration from source to target.

        Calls budprompt service to copy configuration from temporary (with expiry)
        to permanent storage (without expiry).

        Args:
            request: The copy configuration request

        Raises:
            ClientException: If copy operation fails
        """
        try:
            # Call budprompt service to copy the configuration
            return await self._perform_copy_prompt_config_request(request)
        except ClientException:
            raise  # Re-raise ClientException as-is
        except Exception as e:
            logger.exception(f"Failed to copy prompt config: {e}")
            raise ClientException(
                message="Failed to copy prompt configuration", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def _perform_set_default_version_request(self, prompt_id: str, version: int) -> Dict[str, Any]:
        """Perform set default version request to budprompt service.

        Args:
            prompt_id: The prompt ID to set default version for
            version: The version number to set as default

        Returns:
            Response data from budprompt service
        """
        # Build the URL for set-default-version endpoint
        set_default_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_prompt_app_id}/method/v1/prompt/set-default-version"

        # Prepare request payload
        payload = {"prompt_id": prompt_id, "version": version}

        logger.debug(f"Setting default version for prompt_id={prompt_id}, version={version}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(set_default_endpoint, json=payload) as response:
                    response_data = await response.json()

                    if response.status != 200:
                        logger.error(f"Failed to set default version: {response.status} {response_data}")
                        raise ClientException(
                            message=response_data.get("message", "Failed to set default version"),
                            status_code=response.status,
                        )

                    logger.debug(f"Successfully set default version for prompt: {prompt_id}")
                    return response_data

        except aiohttp.ClientError as e:
            logger.exception(f"Network error during set default version request: {e}")
            raise ClientException(
                message="Network error while setting default version",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from e
        except ClientException:
            raise  # Re-raise ClientException as-is
        except Exception as e:
            logger.exception(f"Failed to set default version: {e}")
            raise ClientException(
                message="Failed to set default version", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def _perform_delete_prompt_config_request(
        self, prompt_id: str, version: Optional[int] = None
    ) -> Dict[str, Any]:
        """Perform delete prompt configuration request to budprompt service.

        Args:
            prompt_id: The prompt configuration identifier
            version: Optional version number to delete specific version

        Returns:
            Response data from budprompt service
        """
        # Build the URL for delete endpoint
        delete_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_prompt_app_id}/method/v1/prompt/prompt-config/{prompt_id}"

        # Add version as query parameter if provided
        params = {}
        if version is not None:
            params["version"] = version

        logger.debug(f"Deleting prompt config from budprompt: prompt_id={prompt_id}, version={version}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(delete_endpoint, params=params) as response:
                    response_data = await response.json()

                    if response.status == 404:
                        # It's okay if Redis config doesn't exist when deleting
                        logger.warning(f"Prompt configuration not found in Redis: {prompt_id}")
                        return {"message": "Configuration not found but continuing with database deletion"}
                    elif response.status != 200:
                        logger.error(f"Failed to delete prompt config: {response.status} {response_data}")
                        raise ClientException(
                            message=response_data.get("message", "Failed to delete prompt configuration"),
                            status_code=response.status,
                        )

                    logger.debug(f"Successfully deleted prompt config: {prompt_id}")
                    return response_data

        except aiohttp.ClientError as e:
            logger.exception(f"Network error during delete prompt config request: {e}")
            raise ClientException(
                message="Network error while deleting prompt configuration",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from e
        except ClientException:
            raise  # Re-raise ClientException as-is
        except Exception as e:
            logger.exception(f"Failed to delete prompt config: {e}")
            raise ClientException(
                message="Failed to delete prompt configuration", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def _perform_copy_prompt_config_request(self, request: PromptConfigCopyRequest) -> Dict[str, Any]:
        """Perform the actual copy-config request to budprompt service via Dapr.

        Args:
            request: The copy configuration request

        Returns:
            Response data from budprompt service

        Raises:
            ClientException: If request fails
        """
        copy_config_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_prompt_app_id}/method/v1/prompt/copy-config"
        )

        # Convert request to dict, excluding None values
        payload = request.model_dump(exclude_none=True)

        logger.debug(f"Performing copy config request to budprompt: {payload}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(copy_config_endpoint, json=payload) as response:
                    response_data = await response.json()

                    if response.status != 200:
                        logger.error(f"Failed to copy prompt config: {response.status} {response_data}")
                        raise ClientException(
                            message=response_data.get("message", "Failed to copy prompt configuration"),
                            status_code=response.status,
                        )

                    logger.debug(f"Successfully copied prompt config: {response_data}")
                    return response_data

        except aiohttp.ClientError as e:
            logger.exception(f"Network error during copy prompt config request: {e}")
            raise ClientException(
                message="Network error while copying prompt configuration",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from e
        except ClientException:
            raise  # Re-raise ClientException as-is
        except Exception as e:
            logger.exception(f"Failed to copy prompt config: {e}")
            raise ClientException(
                message="Failed to copy prompt configuration", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e


class PromptWorkflowService(SessionMixin):
    """Service for managing prompt workflows."""

    async def create_prompt_workflow(
        self, current_user_id: UUID, request: CreatePromptWorkflowRequest
    ) -> WorkflowModel:
        """Create a prompt workflow with validation."""
        # Get request data
        current_step_number = request.step_number
        workflow_id = request.workflow_id
        workflow_total_steps = request.workflow_total_steps
        trigger_workflow = request.trigger_workflow
        project_id = request.project_id
        endpoint_id = request.endpoint_id
        name = request.name
        description = request.description
        tags = request.tags
        prompt_type = request.prompt_type
        auto_scale = request.auto_scale
        caching = request.caching
        concurrency = request.concurrency
        rate_limit = request.rate_limit
        rate_limit_value = request.rate_limit_value
        bud_prompt_id = request.bud_prompt_id

        # Retrieve or create workflow
        workflow_create = WorkflowUtilCreate(
            workflow_type=WorkflowTypeEnum.PROMPT_CREATION,
            title="Prompt Creation",
            total_steps=workflow_total_steps,
            icon=APP_ICONS["general"]["deployment_mono"],  # TODO: Add appropriate icon
            tag="Prompt Creation",
        )
        db_workflow = await WorkflowService(self.session).retrieve_or_create_workflow(
            workflow_id, workflow_create, current_user_id
        )

        # If workflow_id exists, check previous steps for project_id and endpoint_id
        previous_project_id = None
        previous_endpoint_id = None
        if workflow_id:
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": workflow_id}
            )
            for step in db_workflow_steps:
                if step.data:
                    if "project_id" in step.data and step.data["project_id"]:
                        previous_project_id = UUID(step.data["project_id"])
                    if "endpoint_id" in step.data and step.data["endpoint_id"]:
                        previous_endpoint_id = UUID(step.data["endpoint_id"])

        # Validate and extract entities if endpoint_id is provided
        model_id = None
        cluster_id = None
        if endpoint_id:
            db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                EndpointModel,
                {"id": endpoint_id},
                exclude_fields={"status": EndpointStatusEnum.DELETED},
                missing_ok=True,
            )
            if not db_endpoint:
                raise ClientException(message="Endpoint not found", status_code=status.HTTP_404_NOT_FOUND)
            model_id = db_endpoint.model_id
            cluster_id = db_endpoint.cluster_id

            # Validate project-endpoint consistency
            if previous_project_id and db_endpoint.project_id != previous_project_id:
                raise ClientException(
                    message="Endpoint does not belong to the specified project.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            # Case 2: Current has both endpoint_id and project_id
            if project_id and db_endpoint.project_id != project_id:
                raise ClientException(
                    message="Endpoint does not belong to the specified project.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Update workflow icon
            if db_endpoint.model.provider_type in [
                ModelProviderTypeEnum.HUGGING_FACE,
                ModelProviderTypeEnum.CLOUD_MODEL,
            ]:
                db_provider = await ProviderDataManager(self.session).retrieve_by_fields(
                    ProviderModel, {"id": db_endpoint.model.provider_id}
                )
                model_icon = db_provider.icon
            else:
                model_icon = db_endpoint.model.icon

            db_workflow = await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"icon": model_icon, "title": db_endpoint.model.name}
            )

        if project_id:
            db_project = await ProjectDataManager(self.session).retrieve_by_fields(
                ProjectModel, {"id": project_id, "status": ProjectStatusEnum.ACTIVE}, missing_ok=True
            )
            if not db_project:
                raise ClientException(message="Project not found", status_code=status.HTTP_404_NOT_FOUND)

            # Validate project-endpoint consistency
            # Case 3: Current has project_id, previous steps have endpoint_id
            if previous_endpoint_id and not endpoint_id:
                # Fetch the previous endpoint to validate
                db_previous_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                    EndpointModel,
                    {"id": previous_endpoint_id},
                    exclude_fields={"status": EndpointStatusEnum.DELETED},
                    missing_ok=True,
                )
                if db_previous_endpoint and db_previous_endpoint.project_id != project_id:
                    raise ClientException(
                        message="Endpoint from previous step belongs to different project",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

            # Update workflow tag
            db_workflow = await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"tag": db_project.name}
            )

        if name:
            db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
                PromptModel, {"name": name, "status": PromptStatusEnum.ACTIVE}, missing_ok=True
            )
            if db_prompt:
                raise ClientException(
                    message="Prompt with this name already exists", status_code=status.HTTP_400_BAD_REQUEST
                )

        # Prepare workflow step data
        workflow_step_data = CreatePromptWorkflowSteps(
            project_id=str(project_id) if project_id else None,
            endpoint_id=str(endpoint_id) if endpoint_id else None,
            model_id=str(model_id) if model_id else None,
            cluster_id=str(cluster_id) if cluster_id else None,
            name=name,
            description=description,
            tags=tags,
            prompt_type=prompt_type.value if prompt_type else None,
            auto_scale=auto_scale,
            caching=caching,
            concurrency=concurrency,
            rate_limit=rate_limit,
            rate_limit_value=rate_limit_value,
            bud_prompt_id=bud_prompt_id,
        ).model_dump(exclude_none=True, exclude_unset=True, mode="json")

        # Create or update workflow step
        await WorkflowStepService(self.session).create_or_update_next_workflow_step(
            db_workflow.id, current_step_number, workflow_step_data
        )

        # Update workflow current step
        await WorkflowDataManager(self.session).update_by_fields(db_workflow, {"current_step": current_step_number})

        # If trigger_workflow is True, create the prompt and version
        if trigger_workflow:
            logger.info("Workflow triggered")

            # Retrieve all step data
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": db_workflow.id}
            )

            # Define the keys required for model deployment
            keys_of_interest = [
                "name",
                "description",
                "tags",
                "project_id",
                "endpoint_id",
                "model_id",
                "cluster_id",
                "prompt_type",
                "auto_scale",
                "caching",
                "concurrency",
                "rate_limit",
                "rate_limit_value",
                "bud_prompt_id",
            ]

            # from workflow steps extract necessary information
            required_data = {}
            for db_workflow_step in db_workflow_steps:
                for key in keys_of_interest:
                    if key in db_workflow_step.data:
                        required_data[key] = db_workflow_step.data[key]

            # Check if all required keys are present
            required_keys = [
                "name",
                "project_id",
                "endpoint_id",
                "concurrency",
                "model_id",
                "bud_prompt_id",
            ]
            missing_keys = [key for key in required_keys if key not in required_data]
            if missing_keys:
                raise ClientException(f"Missing required data: {', '.join(missing_keys)}")

            # Merge all step data
            merged_data = {}
            for step in db_workflow_steps:
                if step.data:
                    merged_data.update(step.data)

            # Ensure uniqueness
            db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
                PromptModel, {"name": merged_data["name"], "status": PromptStatusEnum.ACTIVE}, missing_ok=True
            )
            if db_prompt:
                raise ClientException(
                    message="Prompt with this name already exists", status_code=status.HTTP_400_BAD_REQUEST
                )

            # Copy prompt configuration from temporary to permanent storage
            # This removes the 24hr expiry from the Redis configuration
            if merged_data.get("bud_prompt_id") and merged_data.get("name"):
                try:
                    prompt_service = PromptService(self.session)
                    copy_request = PromptConfigCopyRequest(
                        source_prompt_id=merged_data.get("bud_prompt_id"),
                        source_version=1,
                        target_prompt_id=merged_data.get("name"),
                        target_version=1,
                        replace=True,
                        set_as_default=True,
                    )
                    await prompt_service._copy_prompt_config(copy_request)
                    logger.debug(
                        f"Successfully copied prompt config from {merged_data.get('bud_prompt_id')} to {merged_data.get('name')}"
                    )
                except Exception as e:
                    logger.error(f"Failed to copy prompt configuration: {e}")
                    raise ClientException(
                        message="Failed to copy prompt configuration",
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

            # Create prompt
            db_prompt = await PromptDataManager(self.session).insert_one(
                PromptModel(
                    name=merged_data.get("name"),
                    description=merged_data.get("description"),
                    tags=merged_data.get("tags"),
                    project_id=UUID(merged_data.get("project_id")),
                    prompt_type=merged_data.get("prompt_type", PromptTypeEnum.SIMPLE_PROMPT.value),
                    auto_scale=merged_data.get("auto_scale", False),
                    caching=merged_data.get("caching", False),
                    concurrency=merged_data.get("concurrency"),
                    rate_limit=merged_data.get("rate_limit", False),
                    rate_limit_value=merged_data.get("rate_limit_value"),
                    status=PromptStatusEnum.ACTIVE,
                    created_by=current_user_id,
                )
            )

            # Create first version
            db_version = await PromptVersionDataManager(self.session).insert_one(
                PromptVersionModel(
                    prompt_id=db_prompt.id,
                    endpoint_id=UUID(merged_data.get("endpoint_id")),
                    model_id=UUID(merged_data.get("model_id")),
                    cluster_id=UUID(merged_data.get("cluster_id")) if merged_data.get("cluster_id") else None,
                    version=1,  # First version
                    status=PromptVersionStatusEnum.ACTIVE,
                    created_by=current_user_id,
                )
            )

            # Update prompt with default version
            await PromptDataManager(self.session).update_by_fields(db_prompt, {"default_version_id": db_version.id})

            # Add prompt to proxy cache for routing
            try:
                await self.add_prompt_to_proxy_cache(db_prompt.id, db_prompt.name)
                logger.debug(f"Added prompt {db_prompt.name} to proxy cache")
            except Exception as e:
                logger.error(f"Failed to add prompt to proxy cache: {e}")
                # Continue - cache update is non-critical

            # Update credential proxy cache to include new prompt
            try:
                credential_service = CredentialService(self.session)
                await credential_service.update_proxy_cache(db_prompt.project_id)
                logger.debug(f"Updated credential proxy cache for project {db_prompt.project_id}")
            except Exception as e:
                logger.error(f"Failed to update credential proxy cache: {e}")
                # Continue - cache update is non-critical

            # Store final result in workflow step
            # NOTE: increment step to display success message
            final_step_data = {"prompt_id": str(db_prompt.id), "version_id": str(db_version.id)}
            await WorkflowStepService(self.session).create_or_update_next_workflow_step(
                db_workflow.id, current_step_number + 1, final_step_data
            )

            # Complete workflow
            await WorkflowDataManager(self.session).update_by_fields(
                db_workflow, {"current_step": current_step_number + 1, "status": WorkflowStatusEnum.COMPLETED}
            )

        return db_workflow

    async def create_prompt_schema_workflow(
        self, current_user_id: UUID, request: PromptSchemaRequest, access_token: str
    ) -> WorkflowModel:
        """Create a prompt schema workflow with validation."""
        # Get request data
        current_step_number = request.step_number
        workflow_id = request.workflow_id
        workflow_total_steps = request.workflow_total_steps
        trigger_workflow = request.trigger_workflow
        prompt_id = request.prompt_id
        version = request.version
        set_default = request.set_default
        schema = request.schema
        type = request.type
        deployment_name = request.deployment_name

        # Retrieve or create workflow
        workflow_create = WorkflowUtilCreate(
            workflow_type=WorkflowTypeEnum.PROMPT_SCHEMA_CREATION,
            title="Prompt Schema Creation",
            total_steps=workflow_total_steps,
            icon=APP_ICONS["general"]["deployment_mono"],  # NOTE: Dummy icon
            tag="Prompt Schema Creation",
            visibility=VisibilityEnum.INTERNAL,
        )
        db_workflow = await WorkflowService(self.session).retrieve_or_create_workflow(
            workflow_id, workflow_create, current_user_id
        )

        if workflow_id:
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": workflow_id}
            )

        # Validate deployment_name
        if deployment_name:
            db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                EndpointModel,
                {"name": deployment_name},
                exclude_fields={"status": EndpointStatusEnum.DELETED},
                missing_ok=True,
            )
            if not db_endpoint:
                raise ClientException(message="Deployment not found", status_code=status.HTTP_404_NOT_FOUND)

        # Prepare workflow step data
        workflow_step_data = PromptSchemaWorkflowSteps(
            prompt_id=prompt_id,
            version=version,
            set_default=set_default,
            schema=schema,
            type=type,
            deployment_name=deployment_name,
        ).model_dump(exclude_none=True, exclude_unset=True, mode="json")

        # Create or update workflow step
        await WorkflowStepService(self.session).create_or_update_next_workflow_step(
            db_workflow.id, current_step_number, workflow_step_data
        )

        # Update workflow current step
        await WorkflowDataManager(self.session).update_by_fields(db_workflow, {"current_step": current_step_number})

        # If trigger_workflow is True, create the prompt schema
        if trigger_workflow:
            logger.info("Workflow triggered")

            # Retrieve all step data
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": db_workflow.id}
            )

            # Define the keys required for model deployment
            keys_of_interest = [
                "prompt_id",
                "version",
                "set_default",
                "schema",
                "type",
                "deployment_name",
            ]

            # from workflow steps extract necessary information
            required_data = {}
            for db_workflow_step in db_workflow_steps:
                for key in keys_of_interest:
                    if key in db_workflow_step.data:
                        required_data[key] = db_workflow_step.data[key]

            # Check if all required keys are present
            required_keys = ["schema", "type", "deployment_name"]
            missing_keys = [key for key in required_keys if key not in required_data]
            if missing_keys:
                raise ClientException(f"Missing required data: {', '.join(missing_keys)}")

            # Merge all step data
            merged_data = {}
            for step in db_workflow_steps:
                if step.data:
                    merged_data.update(step.data)

            # Create prompt schema
            try:
                # Perform model extraction
                await self._perform_prompt_schema_creation(
                    current_step_number, merged_data, current_user_id, db_workflow, access_token
                )
            except ClientException as e:
                raise e

        return db_workflow

    async def _perform_prompt_schema_creation(
        self,
        current_step_number: int,
        data: Dict,
        current_user_id: UUID,
        db_workflow: WorkflowModel,
        access_token: str,
    ) -> None:
        """Perform prompt schema creation request to budprompt app.

        Args:
            current_step_number: the current step number in the workflow.
            data: request body to send to budprompt.
            current_user_id: the id of the current user.
            db_workflow: the workflow instance.
            access_token: JWT access token for API key bypass.
        """
        # Fetch endpoint details if deployment_name is provided
        endpoint_id = None
        model_id = None
        project_id = None

        deployment_name = data.get("deployment_name")
        if deployment_name:
            db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                EndpointModel,
                {"name": deployment_name},
                exclude_fields={"status": EndpointStatusEnum.DELETED},
                missing_ok=True,
            )

            if db_endpoint:
                endpoint_id = str(db_endpoint.id)
                model_id = str(db_endpoint.model_id)
                project_id = str(db_endpoint.project_id)

        # Pass the extracted fields to the request
        bud_prompt_schema_response = await self._perform_prompt_schema_request(
            data, current_user_id, db_workflow.id, endpoint_id, model_id, project_id, access_token
        )

        # Add payload dict to response
        for step in bud_prompt_schema_response["steps"]:
            step["payload"] = {}

        prompt_schema_events = {BudServeWorkflowStepEventName.PROMPT_SCHEMA_EVENTS.value: bud_prompt_schema_response}

        current_step_number = current_step_number + 1
        workflow_current_step = current_step_number

        # Update or create next workflow step
        db_workflow_step = await WorkflowStepService(self.session).create_or_update_next_workflow_step(
            db_workflow.id, current_step_number, prompt_schema_events
        )
        logger.debug(f"Workflow step created with id {db_workflow_step.id}")

        # Update progress in workflow
        bud_prompt_schema_response["progress_type"] = BudServeWorkflowStepEventName.MODEL_EXTRACTION_EVENTS.value
        await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"progress": bud_prompt_schema_response, "current_step": workflow_current_step}
        )

    async def _perform_prompt_schema_request(
        self,
        data: Dict[str, Any],
        current_user_id: UUID,
        workflow_id: UUID,
        endpoint_id: Optional[str] = None,
        model_id: Optional[str] = None,
        project_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> Dict:
        """Perform prompt schema creation request to budprompt app.

        Args:
            data: request body to send to budprompt.
            current_user_id: the id of the current user.
            workflow_id: the workflow instance id.
            endpoint_id: the endpoint id for API key bypass.
            model_id: the model id for API key bypass.
            project_id: the project id for API key bypass.
            access_token: JWT access token for API key bypass.
        """
        license_faq_fetch_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_prompt_app_id}/method/v1/prompt/prompt-schema"
        )

        payload = {
            "prompt_id": data.get("prompt_id"),
            "version": data.get("version"),
            "set_default": data.get("set_default"),
            "schema": data.get("schema"),
            "type": data.get("type"),
            "deployment_name": data.get("deployment_name"),
            "notification_metadata": {
                "name": BUD_INTERNAL_WORKFLOW,
                "subscriber_ids": str(current_user_id),
                "workflow_id": str(workflow_id),
            },
            "source_topic": f"{app_settings.source_topic}",
        }

        # Add API key bypass fields if available
        if endpoint_id:
            payload["endpoint_id"] = endpoint_id
        if model_id:
            payload["model_id"] = model_id
        if project_id:
            payload["project_id"] = project_id
            payload["api_key_project_id"] = project_id  # Same as project_id
        if current_user_id:
            payload["user_id"] = str(current_user_id)
        if access_token:
            payload["access_token"] = access_token

        logger.debug(f"Performing create prompt schema request to budprompt {payload}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(license_faq_fetch_endpoint, json=payload) as response:
                    response_data = await response.json()
                    if response.status != 200:
                        logger.error(f"Failed to create prompt schema: {response.status} {response_data}")
                        raise ClientException(
                            "Failed to create prompt schema", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )

                    logger.debug(f"Successfully fetched prompt schema events from budprompt {response_data}")
                    return response_data
        except Exception as e:
            logger.exception(f"Failed to send create prompt schema request: {e}")
            raise ClientException(
                "Failed to create prompt schema", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from e

    async def create_prompt_schema_from_notification_event(self, payload: NotificationPayload) -> None:
        """Create a local model from notification event."""
        logger.debug("Received event for creating local model")

        # Get workflow and steps
        workflow_id = payload.workflow_id
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})

        # Get data from result
        prompt_id = payload.content.result.get("prompt_id")
        prompt_version = payload.content.result.get("version")
        data = {
            "bud_prompt_id": prompt_id,
            "bud_prompt_version": prompt_version,
        }

        # Update prompt_id as next step
        # Update current step number
        current_step_number = db_workflow.current_step + 1
        workflow_current_step = current_step_number

        db_workflow_step = await WorkflowStepService(self.session).create_or_update_next_workflow_step(
            db_workflow.id, current_step_number, data
        )
        logger.debug(f"Upsert workflow step {db_workflow_step.id} for storing prompt schema details")

        # Mark workflow as completed
        logger.debug(f"Marking workflow as completed: {workflow_id}")
        await WorkflowDataManager(self.session).update_by_fields(
            db_workflow, {"status": WorkflowStatusEnum.COMPLETED, "current_step": workflow_current_step}
        )


class PromptVersionService(SessionMixin):
    """Service for managing prompt versions."""

    async def create_prompt_version(
        self, prompt_id: UUID, endpoint_id: UUID, bud_prompt_id: str, set_as_default: bool, current_user_id: UUID
    ) -> PromptVersionModel:
        """Create a new version for an existing prompt."""
        # Validate that the prompt exists and is active
        db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
            PromptModel,
            fields={"id": prompt_id, "status": PromptStatusEnum.ACTIVE},
        )

        if not db_prompt:
            raise ClientException(message="Prompt not found", status_code=status.HTTP_404_NOT_FOUND)

        # Validate and fetch the endpoint
        db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel,
            fields={"id": endpoint_id},
            exclude_fields={"status": EndpointStatusEnum.DELETED},
            missing_ok=True,
        )

        if not db_endpoint:
            raise ClientException(message="Endpoint not found", status_code=status.HTTP_404_NOT_FOUND)

        # Validate that the endpoint belongs to the same project as the prompt
        if db_endpoint.project_id != db_prompt.project_id:
            raise ClientException(
                message="Endpoint does not belong to the same project as the prompt",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Extract model_id and cluster_id from the endpoint
        model_id = db_endpoint.model_id
        cluster_id = db_endpoint.cluster_id

        # Get the next version number
        next_version = await PromptVersionDataManager(self.session).get_next_version(prompt_id)

        # Copy prompt configuration from temporary to permanent storage
        # This removes the 24hr expiry from the Redis configuration
        try:
            prompt_service = PromptService(self.session)
            copy_request = PromptConfigCopyRequest(
                source_prompt_id=bud_prompt_id,
                source_version=1,
                target_prompt_id=db_prompt.name,
                target_version=next_version,
                replace=True,
                set_as_default=set_as_default,
            )
            await prompt_service._copy_prompt_config(copy_request)
            logger.debug(
                f"Successfully copied prompt config from {bud_prompt_id} to {db_prompt.name} version {next_version}"
            )
        except Exception as e:
            logger.error(f"Failed to copy prompt configuration: {e}")
            raise ClientException(
                message="Failed to copy prompt configuration",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Create the new prompt version
        db_version = PromptVersionDataManager(self.session).add_one(
            PromptVersionModel(
                prompt_id=prompt_id,
                endpoint_id=endpoint_id,
                model_id=model_id,
                cluster_id=cluster_id,
                version=next_version,
                status=PromptVersionStatusEnum.ACTIVE,
                created_by=current_user_id,
            )
        )

        # If set_as_default is True, update the prompt's default_version_id
        if set_as_default:
            await PromptDataManager(self.session).update_by_fields(db_prompt, {"default_version_id": db_version.id})
            # Reload the prompt to get the updated default_version
            self.session.refresh(db_prompt)

        # Load relationships for the response
        self.session.refresh(db_version)

        # Convert to response model
        version_response = PromptVersionResponse.model_validate(db_version)

        return version_response

    async def edit_prompt_version(
        self, prompt_id: UUID, version_id: UUID, data: dict[str, Any]
    ) -> PromptVersionResponse:
        """Edit prompt version by validating and updating specific fields."""
        # Retrieve existing prompt version
        db_version = await PromptVersionDataManager(self.session).retrieve_by_fields(
            PromptVersionModel,
            fields={"id": version_id, "prompt_id": prompt_id},
            exclude_fields={"status": PromptVersionStatusEnum.DELETED},
        )

        if not db_version:
            raise ClientException(message="Prompt version not found", status_code=status.HTTP_404_NOT_FOUND)

        # Get the prompt to validate project consistency
        db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
            PromptModel,
            fields={"id": prompt_id, "status": PromptStatusEnum.ACTIVE},
        )

        if not db_prompt:
            raise ClientException(message="Prompt not found", status_code=status.HTTP_404_NOT_FOUND)

        # Handle endpoint_id update if provided
        if "endpoint_id" in data:
            endpoint_id = data["endpoint_id"]

            # Validate and fetch the endpoint
            db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                EndpointModel,
                fields={"id": endpoint_id},
                exclude_fields={"status": EndpointStatusEnum.DELETED},
                missing_ok=True,
            )

            if not db_endpoint:
                raise ClientException(message="Endpoint not found", status_code=status.HTTP_404_NOT_FOUND)

            # Validate that the endpoint belongs to the same project as the prompt
            if db_endpoint.project_id != db_prompt.project_id:
                raise ClientException(
                    message="Endpoint does not belong to the same project as the prompt",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Update model_id and cluster_id from the new endpoint
            data["model_id"] = db_endpoint.model_id
            data["cluster_id"] = db_endpoint.cluster_id

        # Handle set_as_default if provided
        set_as_default = data.pop("set_as_default", None)
        if set_as_default is True:
            # FIRST: Update Redis to set default version
            try:
                prompt_service = PromptService(self.session)
                await prompt_service._perform_set_default_version_request(
                    prompt_id=db_prompt.name,  # Redis uses prompt name as ID
                    version=db_version.version,  # Use the version number
                )
                logger.debug(
                    f"Successfully set default version in Redis for prompt {db_prompt.name} version {db_version.version}"
                )
            except Exception as e:
                logger.error(f"Failed to set default version in Redis: {e}")
                raise ClientException(
                    message="Failed to set default version in configuration service",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # THEN: Update database after Redis is successfully updated
            await PromptDataManager(self.session).update_by_fields(db_prompt, {"default_version_id": db_version.id})

        # Update the prompt version with remaining fields
        if data:  # Only update if there are fields to update
            db_version = await PromptVersionDataManager(self.session).update_by_fields(db_version, data)

        # Load relationships for the response
        self.session.refresh(db_version)

        # Convert to response model
        version_response = PromptVersionResponse.model_validate(db_version)

        return version_response

    async def delete_prompt_version(self, prompt_id: UUID, version_id: UUID) -> None:
        """Delete a prompt version (soft delete) with validation."""
        # Retrieve the prompt to check default version
        db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
            PromptModel,
            fields={"id": prompt_id, "status": PromptStatusEnum.ACTIVE},
        )

        if not db_prompt:
            raise ClientException(message="Prompt not found", status_code=status.HTTP_404_NOT_FOUND)

        # Check if this version is the default version
        if db_prompt.default_version_id == version_id:
            raise ClientException(
                message="Cannot delete the default prompt version",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Retrieve the version to ensure it exists and belongs to this prompt
        db_version = await PromptVersionDataManager(self.session).retrieve_by_fields(
            PromptVersionModel,
            fields={"id": version_id, "prompt_id": prompt_id},
            exclude_fields={"status": PromptVersionStatusEnum.DELETED},
        )

        if not db_version:
            raise ClientException(message="Prompt version not found", status_code=status.HTTP_404_NOT_FOUND)

        # Delete Redis configuration for this specific version BEFORE updating database
        try:
            prompt_service = PromptService(self.session)
            await prompt_service._perform_delete_prompt_config_request(
                prompt_id=db_prompt.name,  # Redis uses prompt name as ID
                version=db_version.version,  # Delete specific version
            )
            logger.debug(f"Deleted Redis configuration for prompt {db_prompt.name} version {db_version.version}")
        except ClientException as e:
            if e.status_code == 404:
                # Redis config might not exist, which is okay
                logger.warning(
                    f"Redis configuration not found for prompt {db_prompt.name} version {db_version.version}: {str(e)}"
                )
            else:
                # Re-raise other errors
                logger.error(
                    f"Failed to delete Redis configuration for prompt {db_prompt.name} version {db_version.version}: {str(e)}"
                )
                raise

        # Soft delete the version by updating its status
        await PromptVersionDataManager(self.session).update_by_fields(
            db_version, {"status": PromptVersionStatusEnum.DELETED}
        )

        logger.debug(f"Soft deleted prompt version {version_id} for prompt {prompt_id}")

        return None

    async def get_prompt_version(
        self, prompt_id: UUID, version_id: UUID
    ) -> tuple[PromptVersionResponse, PromptConfigurationData]:
        """Retrieve a specific prompt version with its configuration from Redis."""
        # Validate that the prompt exists and is active
        db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
            PromptModel,
            fields={"id": prompt_id, "status": PromptStatusEnum.ACTIVE},
        )

        if not db_prompt:
            raise ClientException(message="Prompt not found", status_code=status.HTTP_404_NOT_FOUND)

        # Retrieve the specific version
        db_version = await PromptVersionDataManager(self.session).retrieve_by_fields(
            PromptVersionModel,
            fields={"id": version_id, "prompt_id": prompt_id},
            exclude_fields={"status": PromptVersionStatusEnum.DELETED},
        )

        if not db_version:
            raise ClientException(message="Prompt version not found", status_code=status.HTTP_404_NOT_FOUND)

        # Load relationships for the response
        self.session.refresh(db_version)

        # Create the detailed response
        version_response = PromptVersionResponse.model_validate(db_version)

        # Fetch the prompt configuration from Redis
        # Use the prompt name as the prompt_id for Redis
        try:
            prompt_service = PromptService(self.session)
            response_data = await prompt_service._perform_get_prompt_config_request(db_prompt.name, db_version.version)
            # Parse the configuration data
            config_data = PromptConfigurationData(**response_data.get("data", {}))
        except Exception as e:
            logger.warning(f"Failed to fetch prompt config from Redis: {e}")
            # Return empty config if Redis fetch fails
            config_data = PromptConfigurationData()

        return version_response, config_data

    async def add_prompt_to_proxy_cache(self, prompt_id: UUID, prompt_name: str) -> None:
        """Add prompt to proxy cache for routing through budgateway.

        Args:
            prompt_id: The prompt UUID
            prompt_name: The prompt name to use as model_name
        """
        try:
            # Create BudPromptConfig for the provider
            prompt_config = BudPromptConfig(
                type="budprompt",
                api_base=app_settings.bud_prompt_service_url,
                model_name=prompt_name,
                api_key_location=BUD_PROMPT_API_KEY_LOCATION,
            )

            # Get endpoint name using enum's name property
            endpoint_name = ModelEndpointEnum.RESPONSES.name.lower()  # "responses"

            # Create the proxy model configuration using ProxyModelConfig
            model_config = ProxyModelConfig(
                routing=[ProxyProviderEnum.BUDPROMPT],
                providers={ProxyProviderEnum.BUDPROMPT: prompt_config.model_dump(exclude_none=True)},
                endpoints=[endpoint_name],
                api_key=None,
                pricing=None,  # No pricing for prompts
            )

            # Store in Redis with key pattern matching endpoints
            redis_service = RedisService()
            await redis_service.set(
                f"model_table:{prompt_id}", json.dumps({str(prompt_id): model_config.model_dump(exclude_none=True)})
            )
            logger.debug(f"Added prompt {prompt_name} to proxy cache with key model_table:{prompt_id}")

        except Exception as e:
            logger.error(f"Failed to add prompt to proxy cache: {e}")
            # Don't raise - cache update is non-critical

    async def delete_prompt_from_proxy_cache(self, prompt_id: UUID) -> None:
        """Delete prompt from proxy cache.

        Args:
            prompt_id: The prompt UUID to remove from cache
        """
        try:
            redis_service = RedisService()
            await redis_service.delete_keys_by_pattern(f"model_table:{prompt_id}*")
            logger.debug(f"Deleted prompt {prompt_id} from proxy cache")
        except Exception as e:
            logger.error(f"Failed to delete prompt from proxy cache: {e}")
            # Don't raise - cache cleanup is non-critical
