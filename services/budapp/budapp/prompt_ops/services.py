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
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

import aiohttp
from fastapi import status

from ..commons import logging
from ..commons.config import app_settings, secrets_settings
from ..commons.constants import (
    APP_ICONS,
    BUD_INTERNAL_WORKFLOW,
    BUD_PROMPT_API_KEY_LOCATION,
    CONNECTOR_AUTH_CREDENTIALS_MAP,
    MCP_AUTH_TYPE_MAPPING,
    BudServeWorkflowStepEventName,
    ConnectorAuthTypeEnum,
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
from ..commons.exceptions import ClientException, MCPFoundryException
from ..core.schemas import NotificationPayload
from ..credential_ops.services import CredentialService
from ..endpoint_ops.crud import EndpointDataManager
from ..endpoint_ops.models import Endpoint as EndpointModel
from ..endpoint_ops.schemas import ProxyModelConfig, ProxyModelPricing
from ..model_ops.crud import ProviderDataManager
from ..model_ops.models import Provider as ProviderModel
from ..project_ops.crud import ProjectDataManager
from ..project_ops.models import Project as ProjectModel
from ..shared.mcp_foundry_service import mcp_foundry_service
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
    Connector,
    ConnectorListItem,
    CreatePromptWorkflowRequest,
    CreatePromptWorkflowSteps,
    GatewayResponse,
    HeadersCredentials,
    MCPToolConfig,
    OAuthCredentials,
    OpenCredentials,
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
    TelemetryQueryRequest,
    Tool,
    ToolListItem,
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
                project_id=prompt.project_id,
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

        # Delete from proxy cache (model_table:{prompt_id} - legacy key format)
        try:
            await self.delete_prompt_from_proxy_cache(prompt_id)
            logger.debug(f"Deleted prompt {db_prompt.name} from proxy cache")
        except Exception as e:
            logger.error(f"Failed to delete prompt from proxy cache: {e}")
            # Continue - cache cleanup is non-critical

        # NOTE: update_proxy_cache is called AFTER soft delete below, not here
        # This ensures the prompt is deleted from DB before cache rebuild

        # Delete MCP Foundry gateways from all versions before soft-deleting
        # Query all active versions of this prompt via CRUD layer
        all_versions = await PromptVersionDataManager(self.session).get_active_versions_by_prompt_id(prompt_id)

        # Collect and delete all gateway IDs from all versions
        total_gateways = 0
        for version in all_versions:
            if version.version_metadata and isinstance(version.version_metadata, dict):
                gateway_ids = version.version_metadata.get("gateway_ids", [])

                if gateway_ids:
                    total_gateways += len(gateway_ids)
                    logger.debug(
                        f"Deleting {len(gateway_ids)} MCP Foundry gateways from version {version.version}",
                        gateway_ids=gateway_ids,
                    )

                    for gateway_id in gateway_ids:
                        # delete_gateway already handles 404 gracefully
                        # Any other errors will be raised and propagated
                        await mcp_foundry_service.delete_gateway(gateway_id)
                        logger.debug(f"Successfully deleted MCP Foundry gateway {gateway_id}")

        if total_gateways > 0:
            logger.debug(f"Deleted {total_gateways} total MCP Foundry gateways for prompt {prompt_id}")

        # Delete virtual servers from all versions before soft-deleting
        total_virtual_servers = 0
        for version in all_versions:
            if version.version_metadata and isinstance(version.version_metadata, dict):
                virtual_server_id = version.version_metadata.get("virtual_server_id")

                if virtual_server_id:
                    total_virtual_servers += 1
                    logger.debug(
                        f"Deleting virtual server {virtual_server_id} from version {version.version}",
                    )

                    try:
                        # delete_virtual_server handles 404 gracefully (returns empty dict)
                        await mcp_foundry_service.delete_virtual_server(virtual_server_id)
                        logger.debug(f"Successfully deleted virtual server {virtual_server_id}")
                    except MCPFoundryException as e:
                        # Log error but continue - don't block prompt deletion
                        logger.error(f"Failed to delete virtual server {virtual_server_id}: {e}")

        if total_virtual_servers > 0:
            logger.debug(f"Deleted {total_virtual_servers} total virtual servers for prompt {prompt_id}")

        # Update prompt status to DELETED
        await PromptDataManager(self.session).update_by_fields(db_prompt, {"status": PromptStatusEnum.DELETED})

        # Soft delete all associated prompt versions
        deleted_count = await PromptVersionDataManager(self.session).soft_delete_by_prompt_id(prompt_id)
        logger.debug(f"Soft deleted {deleted_count} prompt versions for prompt {prompt_id}")

        # Update credential proxy cache AFTER soft delete to remove deleted prompt entries
        # This ensures prompt:{name} and prompt:{name}:v{version} keys are removed from cache
        try:
            credential_service = CredentialService(self.session)
            await credential_service.update_proxy_cache(db_prompt.project_id)
            logger.debug(f"Updated credential proxy cache for project {db_prompt.project_id}")
        except Exception as e:
            logger.error(f"Failed to update credential proxy cache: {e}")
            # Continue - cache cleanup is non-critical

        return db_prompt

    async def edit_prompt(self, prompt_id: UUID, data: dict[str, Any]) -> PromptModel:
        """Edit prompt by validating and updating specific fields."""
        # Retrieve existing prompt
        db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
            PromptModel, fields={"id": prompt_id, "status": PromptStatusEnum.ACTIVE}
        )

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

        # If default_version_id was changed, update API key cache for the project
        if "default_version_id" in data and data["default_version_id"]:
            try:
                await CredentialService(self.session).update_proxy_cache(db_prompt.project_id)
                logger.debug(f"Updated credential proxy cache for project {db_prompt.project_id}")
            except Exception as e:
                logger.error(f"Failed to update credential proxy cache: {e}")
                # Continue - cache update is non-critical

        # Convert to response model
        prompt_response = PromptResponse.model_validate(db_prompt)

        return prompt_response

    async def get_prompt(self, prompt_id: UUID) -> PromptResponse:
        """Retrieve a single prompt by ID.

        Args:
            prompt_id: UUID of the prompt to retrieve

        Returns:
            PromptResponse: Prompt details with full relationships

        Raises:
            ClientException: If prompt not found (404) or inactive
        """
        # Retrieve prompt by ID (active only)
        db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
            PromptModel, fields={"id": prompt_id, "status": PromptStatusEnum.ACTIVE}, missing_ok=True
        )

        if not db_prompt:
            raise ClientException(message="Prompt not found", status_code=status.HTTP_404_NOT_FOUND)

        return PromptResponse.model_validate(db_prompt)

    async def list_traces(
        self,
        bud_prompt_id: str,
        project_id: UUID,
        from_date: datetime,
        to_date: datetime,
        page: int = 1,
        limit: int = 50,
        flatten: bool = False,
    ) -> dict:
        """List OTel traces for a prompt with validation.

        Args:
            prompt_id: UUID of the prompt
            project_id: UUID of the project to validate prompt ownership
            from_date: Start date for filtering traces
            to_date: End date for filtering traces
            page: Page number (1-indexed)
            limit: Number of results per page
            flatten: If true, return all spans (root + children) sorted by time

        Returns:
            dict: Response data with items, page, limit, and total_record

        Raises:
            ClientException: If prompt not found or does not belong to project
        """
        # Validate prompt exists and belongs to project
        db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
            PromptModel,
            fields={"name": bud_prompt_id, "project_id": project_id, "status": PromptStatusEnum.ACTIVE},
            missing_ok=True,
        )
        if not db_prompt:
            raise ClientException(
                message="Prompt not found or does not belong to project",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Calculate offset from page (page is 1-indexed)
        offset = (page - 1) * limit

        # Proxy to budmetrics
        traces_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_metrics_app_id}/method/observability/traces"
        )

        params = {
            "resource_type": "prompt",
            "resource_id": str(bud_prompt_id),
            "project_id": str(project_id),
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "offset": offset,
            "limit": limit,
            "flatten": str(flatten).lower(),
        }

        async with aiohttp.ClientSession() as http_session:
            async with http_session.get(traces_endpoint, params=params) as response:
                response_data = await response.json()
                if response.status != 200:
                    logger.error(f"Failed to fetch traces from budmetrics: {response_data}")
                    raise ClientException(
                        message="Failed to fetch traces",
                        status_code=response.status,
                    )

                # Map budmetrics response to PaginatedSuccessResponse format
                return {
                    "items": response_data.get("items", []),
                    "page": page,
                    "limit": limit,
                    "total_record": response_data.get("total_count", 0),
                    "message": "Traces retrieved successfully",
                }

    async def get_trace(
        self,
        bud_prompt_id: str,
        trace_id: str,
        project_id: UUID,
    ) -> dict:
        """Get all spans for a single trace.

        Args:
            bud_prompt_id: Prompt ID for validation
            trace_id: The trace ID to retrieve
            project_id: Project ID for validation

        Returns:
            dict: Response data with trace_id, spans, and total_spans

        Raises:
            ClientException: If prompt not found or does not belong to project
        """
        # Validate prompt exists and belongs to project
        db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
            PromptModel,
            fields={"name": bud_prompt_id, "project_id": project_id, "status": PromptStatusEnum.ACTIVE},
            missing_ok=True,
        )
        if not db_prompt:
            raise ClientException(
                message="Prompt not found or does not belong to project",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Proxy to budmetrics
        trace_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/"
            f"{app_settings.bud_metrics_app_id}/method/observability/traces/{trace_id}"
        )

        async with aiohttp.ClientSession() as http_session:
            async with http_session.get(trace_endpoint) as response:
                response_data = await response.json()
                if response.status != 200:
                    logger.error(f"Failed to fetch trace from budmetrics: {response_data}")
                    raise ClientException(
                        message="Failed to fetch trace",
                        status_code=response.status,
                    )

                return {
                    "trace_id": response_data.get("trace_id", trace_id),
                    "spans": response_data.get("spans", []),
                    "total_spans": response_data.get("total_spans", 0),
                    "message": "Trace retrieved successfully",
                }

    async def query_telemetry(
        self,
        request: TelemetryQueryRequest,
        project_id: str,
    ) -> dict:
        """Query prompt telemetry data via budmetrics.

        Validates prompt ownership, injects project context, and
        forwards the request to budmetrics for query execution.

        Args:
            request: Validated telemetry query request.
            project_id: Project ID from API key context.

        Returns:
            dict: Response data from budmetrics.

        Raises:
            ClientException: If prompt not found or budmetrics call fails.
        """
        # Validate prompt belongs to the project
        db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
            PromptModel,
            fields={
                "name": request.prompt_id,
                "project_id": project_id,
                "status": PromptStatusEnum.ACTIVE,
            },
            missing_ok=True,
        )
        if not db_prompt:
            raise ClientException(
                message="Prompt not found or does not belong to project",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Resolve default version when client omits version
        if request.version is None and db_prompt.default_version_id is not None:
            db_version = await PromptDataManager(self.session).retrieve_by_fields(
                PromptVersionModel,
                fields={"id": db_prompt.default_version_id},
                missing_ok=True,
            )
            request_version = str(db_version.version) if db_version else None
        else:
            request_version = request.version

        # Build payload with server-injected project_id; convert page → offset for budmetrics
        payload = request.model_dump(mode="json", exclude={"page"})
        offset = (request.page - 1) * request.limit
        payload["offset"] = offset
        payload["project_id"] = project_id
        payload["version"] = request_version

        # Forward to budmetrics via Dapr service invocation
        budmetrics_url = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/"
            f"{app_settings.bud_metrics_app_id}/method/"
            f"observability/prompt-telemetry/query"
        )

        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(budmetrics_url, json=payload) as response:
                response_data = await response.json()
                if response.status != 200:
                    logger.error(f"budmetrics telemetry query failed: {response_data}")
                    raise ClientException(
                        message=response_data.get("message", "Telemetry query failed"),
                        status_code=response.status,
                    )

                # Transform response to match budapp pagination convention
                response_data["total_record"] = response_data.pop("total_count", 0)
                response_data["page"] = request.page
                response_data["limit"] = request.limit
                response_data.pop("offset", None)
                response_data.pop("has_more", None)
                response_data.pop("query_time_ms", None)
                response_data["code"] = 200

                return response_data

    async def search_prompt_tags(self, search_term: str, offset: int = 0, limit: int = 10) -> Tuple[List[Dict], int]:
        """Search prompt tags by name."""
        db_tags, count = await PromptDataManager(self.session).search_tags_by_name(search_term, offset, limit)
        return db_tags, count

    async def get_prompt_tags(self, offset: int = 0, limit: int = 10) -> Tuple[List[Dict], int]:
        """Get all prompt tags with pagination."""
        db_tags, count = await PromptDataManager(self.session).get_all_tags(offset, limit)
        return db_tags, count

    async def save_prompt_config(self, request: PromptConfigRequest, current_user_id: UUID) -> PromptConfigResponse:
        """Save prompt configuration by forwarding request to budprompt service.

        Args:
            request: The prompt configuration request
            current_user_id: The ID of the current user creating the draft prompt

        Returns:
            PromptConfigResponse containing the bud_prompt_id and bud_prompt_version
        """
        db_endpoint = None
        db_prompt_version = None
        if request.deployment_name:
            db_endpoint = await EndpointDataManager(self.session).retrieve_by_fields(
                EndpointModel, {"name": request.deployment_name}, exclude_fields={"status": EndpointStatusEnum.DELETED}
            )

            db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
                PromptModel, {"name": request.prompt_id, "status": PromptStatusEnum.ACTIVE}, missing_ok=True
            )

            if db_prompt and db_endpoint:
                # Validate endpoint's project matches
                if db_endpoint.project_id != db_prompt.project_id:
                    raise ClientException(
                        message="Endpoint and prompt must belong to the same project",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
                # Fetch prompt version
                db_prompt_version = await PromptVersionDataManager(self.session).retrieve_by_fields(
                    PromptVersionModel,
                    {"prompt_id": db_prompt.id, "version": request.version},
                    exclude_fields={"status": PromptVersionStatusEnum.DELETED},
                    missing_ok=True,
                )

        # Perform the request to budprompt service
        response_data = await self._perform_prompt_config_request(request)

        # Extract prompt_id and version from the response (dynamic version from budprompt)
        prompt_id = response_data.get("prompt_id")
        version = response_data.get("version")

        # Look up endpoint details from deployment_name for observability
        endpoint_id = None
        model_id = None
        project_id = None

        if db_endpoint:
            endpoint_id = str(db_endpoint.id)
            model_id = str(db_endpoint.model_id)
            project_id = str(db_endpoint.project_id)
            logger.debug(
                f"Resolved endpoint for draft prompt {prompt_id}: endpoint_id={endpoint_id}, "
                f"model_id={model_id}, project_id={project_id}"
            )

        if db_prompt_version:
            self.session.refresh(db_prompt_version)
            db_prompt_version = await PromptVersionDataManager(self.session).update_by_fields(
                db_prompt_version,
                {
                    "endpoint_id": db_endpoint.id,
                    "model_id": db_endpoint.model_id,
                    "cluster_id": db_endpoint.cluster_id,
                },
            )
            logger.debug(
                f"Updated prompt version {request.version} for prompt '{request.prompt_id}' "
                f"with endpoint_id={db_endpoint.id}"
            )

            # Update Redis Cache
            try:
                await CredentialService(self.session).update_proxy_cache(db_prompt.project_id)
                logger.debug(f"Updated proxy cache for project {db_prompt.project_id}")
            except Exception as e:
                logger.warning(f"Failed to update proxy cache: {e}", exc_info=True)
                # Don't fail the request if cache update fails - DB is already updated

        # Save draft prompt reference for playground access with version-specific key
        try:
            redis_service = RedisService()
            # Include version in draft key (similar to regular prompts: prompt:{name}:v{version})
            draft_key = f"draft_prompt:{current_user_id}:{prompt_id}:v{version}"
            draft_value = json.dumps(
                {
                    "prompt_id": prompt_id,
                    "user_id": str(current_user_id),
                    "endpoint_id": endpoint_id,  # From endpoint lookup
                    "model_id": model_id,  # From endpoint lookup
                    "project_id": project_id,  # From endpoint lookup
                    "version": version,  # Dynamic version from budprompt response
                }
            )
            # Set TTL to 24 hours (86400 seconds) - matching budprompt temporary storage
            await redis_service.set(draft_key, draft_value, ex=app_settings.prompt_config_redis_ttl)

            # Add to proxy cache for routing (prompt_name = prompt_id for draft prompts)
            await PromptWorkflowService(self.session).add_prompt_to_proxy_cache(
                prompt_id, prompt_id, ex=app_settings.prompt_config_redis_ttl
            )
            logger.debug(f"Added draft prompt {prompt_id} v{version} to cache for user {current_user_id}")
        except Exception as e:
            logger.error(f"Failed to cache draft prompt: {e}")
            # Don't fail the request if caching fails

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

    async def get_prompt_config(self, prompt_id: str, version: int) -> PromptConfigGetResponse:
        """Get prompt configuration from budprompt service.

        Args:
            prompt_id: The prompt configuration identifier
            version: Version number to retrieve

        Returns:
            PromptConfigGetResponse containing the configuration data
        """
        try:
            # Perform the request to budprompt service
            response_data = await self._perform_get_prompt_config_request(prompt_id, version)

            # Parse the configuration data
            config_data = PromptConfigurationData(**response_data.get("data", {}))
            response_version = response_data.get("version")
            response_message = "Prompt configuration retrieved successfully"
        except ClientException as e:
            if e.status_code == 404:
                # NOTE: Return empty/default config as requested for Frontend logic
                logger.debug("Prompt config not found for %s, returning empty config", prompt_id)
                config_data = PromptConfigurationData()
                response_version = version  # Use original parameter
                response_message = "Prompt configuration not found, returning empty config"
            else:
                raise  # Re-raise non-404 errors

        # Create and return response
        return PromptConfigGetResponse(
            prompt_id=prompt_id,
            data=config_data,
            version=response_version,
            message=response_message,
            code=status.HTTP_200_OK,
        )

    async def _perform_get_prompt_config_request(
        self, prompt_id: str, version: Optional[int] = None, raw_data: bool = False
    ) -> Dict[str, Any]:
        """Perform get prompt configuration request to budprompt service.

        Args:
            prompt_id: The prompt configuration identifier
            version: Optional version number
            raw_data: If True, returns raw data from Redis without Pydantic processing

        Returns:
            Response data from budprompt service
        """
        # Build the URL with optional version query parameter
        prompt_config_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_prompt_app_id}/method/v1/prompt/prompt-config/{prompt_id}"

        # Add version and raw_data as query parameters if provided
        params = {}
        if version is not None:
            params["version"] = version
        if raw_data:
            params["raw_data"] = "true"

        logger.debug(
            f"Retrieving prompt config from budprompt: prompt_id={prompt_id}, version={version}, raw_data={raw_data}"
        )

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

    async def get_connectors(
        self,
        prompt_id: Optional[str] = None,
        is_registered: Optional[bool] = None,
        version: Optional[int] = None,
        offset: int = 0,
        limit: int = 10,
        filters: dict = {},
        order_by: list = [],
        search: bool = False,
    ) -> tuple[list[ConnectorListItem], int]:
        """Get connectors list from MCP Foundry.

        Args:
            prompt_id: Optional prompt ID (UUID or draft ID) to filter connectors for a specific prompt
            is_registered: Optional filter for registration status (only works with prompt_id)
                - True: Show only registered connectors
                - False: Show only non-registered connectors
                - None: Show all connectors
            version: Optional version number. If not specified, uses default version
            offset: Pagination offset
            limit: Pagination limit
            filters: Additional filters
            order_by: Ordering fields
            search: Enable search functionality

        Returns:
            Tuple of (list of connectors, total count)
        """
        # Extract name filter if provided
        name_filter = filters.get("name")

        if prompt_id:
            # Get registered connector IDs from Redis if prompt_id provided
            registered_connector_ids = set()

            # Fetch prompt configuration from Redis to get registered connectors
            try:
                # Pass version parameter (None for default version)
                config_response = await self._perform_get_prompt_config_request(prompt_id, version=version)
                config_data = config_response.get("data", {})
                tools = config_data.get("tools", [])

                # Get the actual version from response
                actual_version = config_response.get("version", version or 1)

                # Extract connector IDs from gateway_config in each tool
                for tool in tools:
                    if tool.get("type") == "mcp":
                        gateway_config = tool.get("gateway_config", {})
                        # gateway_config is {connector_id: gateway_id}
                        registered_connector_ids.update(gateway_config.keys())

                logger.debug(
                    f"Found {len(registered_connector_ids)} registered connectors "
                    f"for prompt {prompt_id} version {actual_version}"
                )

            except ClientException as e:
                if e.status_code == 404:
                    # No config found, no registered connectors
                    logger.debug(
                        f"No configuration found for prompt {prompt_id} "
                        f"{'version ' + str(version) if version else '(default version)'}, "
                        f"returning empty list"
                    )
                    registered_connector_ids = set()
                else:
                    raise

            # Call MCP Foundry API based on is_registered filter
            try:
                if is_registered is True:
                    # Show only registered connectors - use list_connectors_by_connector_ids
                    logger.debug(f"Filtering to show only registered connectors for prompt {prompt_id}")
                    mcp_foundry_response, total_count = await mcp_foundry_service.list_connectors_by_connector_ids(
                        connector_ids=list(registered_connector_ids),
                        show_registered_only=False,
                        show_available_only=True,
                        name=name_filter,
                        offset=offset,
                        limit=limit,
                    )
                    logger.debug(f"Successfully fetched {total_count} registered connectors from MCP Foundry")

                elif is_registered is False:
                    # Show only non-registered connectors - fetch all connectors then filter
                    logger.debug(f"Filtering to show only non-registered connectors for prompt {prompt_id}")

                    # Fetch ALL connectors using pagination loop
                    all_connectors = []
                    page_size = 100  # Fetch in batches of 100
                    fetch_offset = 0

                    while True:
                        # Fetch a page of connectors
                        batch_connectors, total = await mcp_foundry_service.list_connectors(
                            show_registered_only=False,
                            show_available_only=True,
                            name=name_filter,
                            offset=fetch_offset,
                            limit=page_size,
                        )

                        # Add to our list
                        all_connectors.extend(batch_connectors)

                        # Update offset
                        fetch_offset += page_size

                        # Break if we've fetched all connectors
                        if fetch_offset >= total or len(batch_connectors) == 0:
                            break

                    logger.debug(f"Fetched {len(all_connectors)} total connectors from MCP Foundry")

                    # Filter out registered connector IDs
                    filtered_connectors = [
                        connector
                        for connector in all_connectors
                        if connector.get("id") not in registered_connector_ids
                    ]

                    # Calculate total count of filtered connectors
                    total_count = len(filtered_connectors)

                    # Apply pagination to filtered results
                    mcp_foundry_response = filtered_connectors[offset : offset + limit]

                    logger.debug(
                        f"Filtered to {total_count} non-registered connectors, "
                        f"returning {len(mcp_foundry_response)} for page {(offset // limit) + 1}"
                    )

                else:
                    # Show all connectors (current behavior when is_registered not specified)
                    logger.debug(f"Showing all connectors for prompt {prompt_id}")
                    mcp_foundry_response, total_count = await mcp_foundry_service.list_connectors(
                        show_registered_only=False,
                        show_available_only=True,
                        name=name_filter,
                        offset=offset,
                        limit=limit,
                    )
                    logger.debug(f"Successfully fetched {total_count} connectors from MCP Foundry")
            except MCPFoundryException as e:
                logger.error(f"MCP Foundry API error: {e}")
                mcp_foundry_response = []
                total_count = 0
            except Exception as e:
                logger.error(f"Unexpected error calling MCP Foundry: {e}")
                mcp_foundry_response = []
                total_count = 0
        else:
            logger.debug(
                f"Fetching connectors from MCP Foundry{f' with name filter: {name_filter}' if name_filter else ''}"
            )

            # Call MCP Foundry API
            try:
                mcp_foundry_response, total_count = await mcp_foundry_service.list_connectors(
                    show_registered_only=False, show_available_only=True, name=name_filter, offset=offset, limit=limit
                )
                logger.debug(f"Successfully fetched {total_count} connectors from MCP Foundry")
            except MCPFoundryException as e:
                logger.error(f"MCP Foundry API error: {e}")
                mcp_foundry_response = []
                total_count = 0
            except Exception as e:
                logger.error(f"Unexpected error calling MCP Foundry: {e}")
                mcp_foundry_response = []
                total_count = 0

        # Map MCP response to ConnectorListItem
        connector_items = []
        for item in mcp_foundry_response:
            try:
                connector_item = ConnectorListItem(
                    id=item.get("id", ""),
                    name=item.get("name", ""),
                    icon=item.get("logo_url"),
                    category=item.get("category"),
                    url=item.get("url", ""),
                    provider=item.get("provider", ""),
                    description=item.get("description"),
                    documentation_url=item.get("documentation_url"),
                )
                connector_items.append(connector_item)
            except (ValueError, KeyError) as e:
                logger.error(f"Found invalid connector item: {e}")
                continue

        return connector_items, total_count

    async def get_connector_by_id(self, connector_id: str) -> Connector:
        """Get a single connector by its ID from MCP Foundry.

        Args:
            connector_id: String ID of the connector (e.g., "github", "slack")

        Returns:
            Connector object with full details

        Raises:
            ClientException: If connector not found
        """
        logger.debug(f"Getting connector with ID: {connector_id}")

        try:
            # Use the new get_connector_by_id method which fetches all connectors with pagination
            connector_data = await mcp_foundry_service.get_connector_by_id(connector_id)

            # Map MCP Foundry auth_type to our enum using mapping table
            auth_type_str = connector_data.get("auth_type", "Open")
            auth_type = MCP_AUTH_TYPE_MAPPING.get(auth_type_str, ConnectorAuthTypeEnum.OPEN)

            # Get credential schema based on auth type
            credential_schema = CONNECTOR_AUTH_CREDENTIALS_MAP.get(auth_type, [])

            # Build Connector object
            connector = Connector(
                id=connector_data.get("id", ""),
                name=connector_data.get("name", ""),
                icon=connector_data.get("logo_url"),
                category=connector_data.get("category"),
                url=connector_data.get("url", ""),
                provider=connector_data.get("provider", ""),
                description=connector_data.get("description"),
                documentation_url=connector_data.get("documentation_url"),
                auth_type=auth_type,
                credential_schema=credential_schema,
            )

            logger.debug(f"Successfully retrieved connector: {connector.name}")
            return connector

        except MCPFoundryException as e:
            logger.error(f"MCP Foundry error getting connector {connector_id}: {e}")
            raise ClientException(
                message=f"Failed to retrieve connector: {str(e)}", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except ClientException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting connector {connector_id}: {e}")
            raise ClientException(
                message="Failed to retrieve connector", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    async def _check_connector_already_registered(
        self, budprompt_id: str, connector_id: str, version: Optional[int] = None
    ) -> tuple[bool, dict]:
        """Check if a connector is already registered for a prompt.

        Args:
            budprompt_id: The bud prompt ID (can be UUID or draft prompt ID)
            connector_id: The connector ID to check
            version: Optional version to check. If None, checks default version

        Returns:
            Tuple of (is_registered: bool, config_response: dict)
            - is_registered: True if connector already registered, False otherwise
            - config_response: The full prompt config response dict (empty dict if 404)
        """
        try:
            config_response = await self._perform_get_prompt_config_request(
                budprompt_id, version=version, raw_data=True
            )
            config_data = config_response.get("data", {})
            tools = config_data.get("tools", [])

            # Check if connector_id exists in any tool's gateway_config
            for tool in tools:
                if tool.get("type") == "mcp":
                    gateway_config = tool.get("gateway_config", {})
                    if connector_id in gateway_config:
                        return True, config_response

            return False, config_response

        except ClientException as e:
            if e.status_code == 404:
                # No config exists, connector not registered
                return False, {}
            else:
                # Re-raise other errors
                raise

    def _detect_transport_from_url(self, url: str) -> str:
        """Detect transport type from connector URL.

        Args:
            url: Connector URL

        Returns:
            "SSE" if URL ends with /sse, otherwise "STREAMABLEHTTP"
        """
        normalized_url = url.rstrip("/")
        if normalized_url.endswith("/sse"):
            return "SSE"
        else:
            return "STREAMABLEHTTP"

    def _transform_credentials_to_mcp_format(
        self, credentials: Union[OAuthCredentials, HeadersCredentials, OpenCredentials]
    ) -> Dict[str, Any]:
        """Transform credentials to MCP Foundry gateway payload format.

        Args:
            credentials: Typed credentials object

        Returns:
            Dictionary with auth configuration for MCP Foundry API

        Raises:
            ClientException: If transformation fails or unsupported auth type
        """
        auth_config: Dict[str, Any] = {}

        if isinstance(credentials, OAuthCredentials):
            # Build OAuth configuration
            oauth_config = {
                "grant_type": credentials.grant_type,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "token_url": credentials.token_url,
                "authorization_url": credentials.authorization_url,
                "redirect_uri": credentials.redirect_uri,
                # Add token management inside oauth_config
                "token_management": {
                    "store_tokens": True,
                    "auto_refresh": True,
                    "refresh_threshold_seconds": 300,
                },
            }

            # Add optional scopes if provided
            if credentials.scopes:
                oauth_config["scopes"] = credentials.scopes

            # Set auth_type and oauth_config at root level
            auth_config["auth_type"] = "oauth"
            auth_config["oauth_config"] = oauth_config

            # Add passthrough headers if provided
            if credentials.passthrough_headers:
                auth_config["passthrough_headers"] = credentials.passthrough_headers

        elif isinstance(credentials, HeadersCredentials):
            # Headers authentication uses "authheaders" type in MCP Foundry
            auth_config["auth_type"] = "authheaders"
            auth_config["auth_headers"] = credentials.auth_headers

            # Add OAuth-related fields required by MCP Foundry
            auth_config["oauth_grant_type"] = "client_credentials"
            auth_config["oauth_store_tokens"] = True
            auth_config["oauth_auto_refresh"] = True

            # Add passthrough headers if provided
            if credentials.passthrough_headers:
                auth_config["passthrough_headers"] = credentials.passthrough_headers

        elif isinstance(credentials, OpenCredentials):
            # Open authentication - add OAuth fields required by MCP Foundry
            auth_config["oauth_grant_type"] = "client_credentials"
            auth_config["oauth_store_tokens"] = True
            auth_config["oauth_auto_refresh"] = True

            # Add passthrough headers if provided
            if credentials.passthrough_headers:
                auth_config["passthrough_headers"] = credentials.passthrough_headers

        else:
            raise ClientException(
                message=f"Unsupported credential type: {type(credentials).__name__}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return auth_config

    async def register_connector_for_prompt(
        self,
        budprompt_id: str,
        connector_id: str,
        credentials: Union[OAuthCredentials, HeadersCredentials, OpenCredentials],
        version: Optional[int] = None,
        permanent: bool = False,
    ) -> GatewayResponse:
        """Register a connector for a prompt by creating gateway in MCP Foundry.

        Args:
            budprompt_id: The bud prompt ID (can be UUID or draft prompt ID)
            connector_id: The connector ID to register
            credentials: Connector credentials based on auth_type
            version: Optional version to update. If None, updates default version
            permanent: Store configuration permanently without expiration

        Returns:
            gateway

        Raises:
            ClientException: If connector not found or gateway creation fails
        """
        logger.debug(f"Registering connector {connector_id} for prompt {budprompt_id}")

        # Check if connector is already registered and get full config response
        is_registered, config_response = await self._check_connector_already_registered(
            budprompt_id, connector_id, version
        )

        # Extract config data from response
        config_data = config_response.get("data", {})

        if is_registered:
            logger.error(f"Connector {connector_id} is already registered for prompt {budprompt_id}")
            raise ClientException(
                message="Connector is already registered for prompt",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Validate allow_multiple_calls if config exists (before creating gateway)
        if config_data:  # Config exists
            allow_multiple_calls = config_data.get("allow_multiple_calls", False)
            if not allow_multiple_calls:
                logger.error(f"Cannot register connector: allow_multiple_calls is disabled for prompt {budprompt_id}")
                raise ClientException(
                    message="Allow Multiple Calls must be enabled for MCP tool usage",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        # Determine target version based on priority:
        # 1. User-specified version (highest priority)
        # 2. Existing config version (medium priority)
        # 3. Default to version 1 (lowest priority - new config)
        existing_version = config_response.get("version")

        if version:
            # User explicitly specified version
            target_version = version
        elif existing_version:
            # Use existing config version
            target_version = existing_version
        else:
            # Default to version 1 for new configs
            target_version = 1

        # Get connector details from MCP Foundry
        try:
            connector = await self.get_connector_by_id(connector_id)
        except ClientException as e:
            logger.error(f"Failed to retrieve connector {connector_id}: {e}")
            raise

        # Validate credentials match connector's auth_type
        if isinstance(credentials, OAuthCredentials) and connector.auth_type != ConnectorAuthTypeEnum.OAUTH:
            raise ClientException(
                message=f"Credential type mismatch: connector '{connector_id}' requires '{connector.auth_type.value}' authentication but 'OAuth' credentials provided",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        elif isinstance(credentials, HeadersCredentials) and connector.auth_type != ConnectorAuthTypeEnum.HEADERS:
            raise ClientException(
                message=f"Credential type mismatch: connector '{connector_id}' requires '{connector.auth_type.value}' authentication but 'Headers' credentials provided",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        elif isinstance(credentials, OpenCredentials) and connector.auth_type != ConnectorAuthTypeEnum.OPEN:
            raise ClientException(
                message=f"Credential type mismatch: connector '{connector_id}' requires '{connector.auth_type.value}' authentication but 'Open' credentials provided",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Construct gateway name: {budprompt_id}__v{version}__{connector_id}
        # Using double underscore as separator (MCP Foundry only allows letters, numbers, _, -)
        gateway_name = f"{budprompt_id}__v{target_version}__{connector_id}"

        # Detect transport from connector URL
        transport = self._detect_transport_from_url(connector.url)

        # Transform credentials to MCP Foundry format
        auth_config = self._transform_credentials_to_mcp_format(credentials)

        # Create gateway in MCP Foundry
        try:
            gateway_response = await mcp_foundry_service.create_gateway(
                name=gateway_name, url=connector.url, transport=transport, visibility="public", auth_config=auth_config
            )

            gateway_id = gateway_response.get("id", gateway_response.get("gateway_id"))
            gateway_slug = gateway_response.get("slug")

            logger.debug(
                f"Successfully created gateway for connector {connector_id} and prompt {budprompt_id}",
                gateway_id=gateway_id,
                gateway_slug=gateway_slug,
            )

            # Create GatewayResponse object
            gateway = GatewayResponse(
                gateway_id=gateway_id,
                name=gateway_name,
                url=connector.url,
                transport="SSE",
                visibility="public",
            )

            # Store MCP tool configuration in Redis via budprompt service
            await self._store_mcp_tool_config(
                budprompt_id, connector_id, gateway.gateway_id, gateway_slug, version, permanent
            )

            # Update PromptVersion metadata with gateway_id (if prompt and version exist in DB)
            try:
                # Check if prompt exists by name (budprompt_id is the prompt name)
                db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
                    PromptModel,
                    fields={"name": budprompt_id, "status": PromptStatusEnum.ACTIVE},
                    missing_ok=True,
                )

                if db_prompt:
                    # Check if prompt_version exists
                    db_prompt_version = await PromptVersionDataManager(self.session).retrieve_by_fields(
                        PromptVersionModel,
                        fields={"prompt_id": db_prompt.id, "version": int(target_version)},
                        missing_ok=True,
                    )

                    if db_prompt_version:
                        # Get existing metadata (default is empty dict from migration)
                        existing_metadata = (
                            db_prompt_version.version_metadata
                            if isinstance(db_prompt_version.version_metadata, dict)
                            else {}
                        )

                        # Initialize gateway_ids array if not present
                        if "gateway_ids" not in existing_metadata:
                            existing_metadata["gateway_ids"] = []

                        # Append newly created gateway_id (avoid duplicates)
                        if gateway.gateway_id not in existing_metadata["gateway_ids"]:
                            existing_metadata["gateway_ids"].append(gateway.gateway_id)

                        # Update the prompt_version record using async pattern
                        self.session.refresh(db_prompt_version)
                        db_prompt_version = await PromptVersionDataManager(self.session).update_by_fields(
                            db_prompt_version, {"version_metadata": existing_metadata}
                        )

                        logger.debug(
                            f"Updated prompt_version metadata with gateway_id {gateway.gateway_id}",
                            prompt_id=db_prompt.id,
                            version=int(target_version),
                        )
            except Exception as e:
                # Silent failure - don't block connector registration if DB update fails
                logger.warning(f"Failed to update prompt_version metadata: {e}", exc_info=True)

            return gateway

        except MCPFoundryException as e:
            logger.error(f"MCP Foundry error creating gateway: {e}")
            raise ClientException(
                message="Failed to create mcp gateway.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error(f"Unexpected error registering connector: {e}")
            raise ClientException(
                message="Failed to register connector", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    async def add_tool_for_prompt(
        self,
        prompt_id: str,
        connector_id: str,
        tool_ids: List[str],
        version: Optional[int] = None,
        permanent: bool = False,
    ) -> Dict[str, Any]:
        """Add tools for a prompt by creating/updating virtual server in MCP Foundry.

        Args:
            prompt_id: The prompt ID (UUID or draft ID)
            connector_id: The connector ID
            tool_ids: List of tool IDs to add (replaces existing tools)
            version: Optional version to update. If None, uses default version
            permanent: Store configuration permanently without expiration

        Returns:
            Dict with virtual_server_id, virtual_server_name, added_tools, and action
            virtual_server_name format: {prompt_id}__v{version}

        Raises:
            ClientException: If prompt not found (404) or operation fails
        """
        logger.debug(f"Adding tools for prompt {prompt_id}, connector {connector_id}")

        # Convert UUID tool_ids to hex strings for MCP Foundry and Redis storage
        tool_ids_str = [str(tool_id.hex) for tool_id in tool_ids]

        # Step 1: Fetch existing prompt configuration (must exist)
        try:
            config_response = await self._perform_get_prompt_config_request(prompt_id, version=version, raw_data=True)
            config_data = config_response.get("data", {})
            tools = config_data.get("tools", [])
            # Determine target version for virtual server naming
            target_version = config_response.get("version", 1) if version is None else version
        except ClientException:
            raise

        # Step 2: Find MCP tool and validate connector
        mcp_tool = None
        mcp_tool_index = None

        for index, tool in enumerate(tools):
            if tool.get("type") == "mcp":
                mcp_tool = tool
                mcp_tool_index = index
                break

        if not mcp_tool:
            logger.error(f"MCP tool configuration not found for prompt {prompt_id}")
            raise ClientException(
                message="MCP tool configuration not found for this prompt",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        gateway_config = mcp_tool.get("gateway_config", {})
        if connector_id not in gateway_config:
            logger.error(f"Connector {connector_id} not registered for prompt {prompt_id}")
            raise ClientException(
                message=f"Connector {connector_id} is not registered for this prompt",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Step 3: Merge new tool IDs into existing server_config
        existing_server_config = mcp_tool.get("server_config", {})
        existing_server_config[connector_id] = tool_ids_str

        # Step 4: Collect ALL tool IDs from ALL connectors
        all_tool_ids = []
        for _conn_id, conn_tool_ids in existing_server_config.items():
            all_tool_ids.extend(conn_tool_ids)

        logger.debug(f"Total tools across all connectors: {len(all_tool_ids)}")

        # Step 5: Fetch original names and names for ALL tool IDs (not just newly added)
        all_tool_original_names = []
        all_tool_names = []
        for tool_id in all_tool_ids:
            try:
                tool_data = await mcp_foundry_service.get_tool_by_id(tool_id)
                original_name = tool_data["originalName"]
                tool_name = tool_data["name"]
                all_tool_original_names.append(original_name)
                all_tool_names.append(tool_name)
            except MCPFoundryException as e:
                logger.error(f"Failed to fetch tool {tool_id}: {e}")
                raise ClientException(message="Tool not found", status_code=status.HTTP_404_NOT_FOUND)
            except KeyError as e:
                logger.error(f"Tool {tool_id} missing required field: {e}")
                raise ClientException(
                    message="Invalid tool data",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # Step 6: Create or update virtual server with ALL tools
        virtual_server_id = mcp_tool.get("server_url")

        # Construct virtual server name: {prompt_id}__v{version}
        virtual_server_name = f"{prompt_id}__v{target_version}"

        try:
            if virtual_server_id:
                # Update existing virtual server with ALL tools from ALL connectors
                logger.debug(f"Updating virtual server {virtual_server_id} with {len(all_tool_ids)} tools")
                await mcp_foundry_service.update_virtual_server(
                    server_id=virtual_server_id, associated_tools=all_tool_ids
                )
            else:
                # Create new virtual server with ALL tools
                logger.debug(f"Creating virtual server for prompt {prompt_id} version {target_version}")
                vs_response = await mcp_foundry_service.create_virtual_server(
                    name=virtual_server_name, associated_tools=all_tool_ids, visibility="public"
                )
                virtual_server_id = vs_response.get("id")

            # Update MCP tool config with merged data
            mcp_tool["server_label"] = virtual_server_name
            mcp_tool["server_url"] = virtual_server_id
            mcp_tool["allowed_tools"] = all_tool_original_names  # All tool original names
            mcp_tool["allowed_tool_names"] = all_tool_names  # All tool names
            mcp_tool["connector_id"] = virtual_server_id
            mcp_tool["server_config"] = existing_server_config  # Merged server_config
            tools[mcp_tool_index] = mcp_tool

        except MCPFoundryException as e:
            logger.error(f"MCP Foundry error: {e}")
            raise ClientException(
                message="Failed to create/update virtual server",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Step 7: Save updated configuration to Redis
        # Preserve all existing config data, only update tools field
        payload = {
            **config_data,  # Spread all existing fields
            "prompt_id": prompt_id,
            "version": target_version,
            "set_default": False,  # Don't change default for existing configs
            "tools": tools,  # Override tools field
            "permanent": permanent,  # Control TTL
        }

        # Save using helper method
        await self._save_prompt_config_to_redis(payload)

        # Step 7.5: Update PromptVersion metadata with virtual_server_id (if prompt and version exist in DB)
        try:
            # Check if prompt exists by name (prompt_id is the prompt name)
            db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
                PromptModel,
                fields={"name": prompt_id, "status": PromptStatusEnum.ACTIVE},
                missing_ok=True,
            )

            if db_prompt:
                # Check if prompt_version exists
                db_prompt_version = await PromptVersionDataManager(self.session).retrieve_by_fields(
                    PromptVersionModel,
                    fields={"prompt_id": db_prompt.id, "version": int(target_version)},
                    missing_ok=True,
                )

                if db_prompt_version:
                    # Get existing metadata (default is empty dict from migration)
                    existing_metadata = (
                        db_prompt_version.version_metadata
                        if isinstance(db_prompt_version.version_metadata, dict)
                        else {}
                    )

                    # Store virtual_server_id (single value, not array - only one VS per version)
                    existing_metadata["virtual_server_id"] = virtual_server_id

                    # Update the prompt_version record using async pattern
                    self.session.refresh(db_prompt_version)
                    db_prompt_version = await PromptVersionDataManager(self.session).update_by_fields(
                        db_prompt_version, {"version_metadata": existing_metadata}
                    )

                    logger.debug(
                        f"Updated prompt_version metadata with virtual_server_id {virtual_server_id}",
                        prompt_id=db_prompt.id,
                        version=int(target_version),
                    )
        except Exception as e:
            # Silent failure - don't block tool addition if DB update fails
            logger.warning(f"Failed to update prompt_version metadata with virtual_server_id: {e}", exc_info=True)

        # Step 8: Return response
        return {
            "virtual_server_id": virtual_server_id,
            "virtual_server_name": virtual_server_name,
            "added_tools": tool_ids_str,
        }

    async def disconnect_connector_from_prompt(
        self, budprompt_id: str, connector_id: str, version: Optional[int] = None, permanent: bool = False
    ) -> Dict[str, Any]:
        """Disconnect a connector from a prompt by deleting gateway and cleaning config.

        Args:
            budprompt_id: The bud prompt ID (UUID or draft ID)
            connector_id: The connector ID to disconnect
            permanent: Store configuration permanently without expiration
            version: Optional version to update. If None, updates default version

        Returns:
            Dict with deletion details

        Raises:
            ClientException: If prompt not found or connector not registered
        """
        logger.debug(f"Disconnecting connector {connector_id} from prompt {budprompt_id}")

        # Step 1: Fetch prompt config from Redis
        config_response = await self._perform_get_prompt_config_request(budprompt_id, version=version, raw_data=True)
        config_data = config_response.get("data", {})
        tools = config_data.get("tools", [])
        target_version = config_response.get("version", 1) if version is None else version

        # Step 2: Find MCP tool config and validate connector is registered
        mcp_tool = None
        mcp_tool_index = None

        for index, tool in enumerate(tools):
            if tool.get("type") == "mcp":
                mcp_tool = tool
                mcp_tool_index = index
                break

        if not mcp_tool:
            raise ClientException(
                message="No MCP connectors registered for this prompt",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        gateway_config = mcp_tool.get("gateway_config", {})
        if connector_id not in gateway_config:
            raise ClientException(
                message=f"Connector {connector_id} is not registered for this prompt",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        gateway_id = gateway_config[connector_id]
        server_config = mcp_tool.get("server_config", {})
        tool_ids_to_remove = server_config.get(connector_id, [])

        # Step 3: Fetch tool originalNames and names BEFORE deleting gateway
        # (Once gateway is deleted, tools are removed from MCP Foundry)
        tool_original_names_to_remove = []
        tool_names_to_remove = []
        for tool_id in tool_ids_to_remove:
            try:
                tool_data = await mcp_foundry_service.get_tool_by_id(tool_id)
                original_name = tool_data["originalName"]
                tool_name = tool_data["name"]
                tool_original_names_to_remove.append(original_name)
                tool_names_to_remove.append(tool_name)
            except Exception as e:
                logger.warning(
                    f"Could not fetch tool {tool_id} to remove from allowed_tools and allowed_tool_names: {e}"
                )

        # Step 4: Delete gateway in MCP Foundry (auto-removes tools from virtual server)
        try:
            await mcp_foundry_service.delete_gateway(gateway_id)
            logger.debug(f"Successfully deleted gateway {gateway_id}")
        except MCPFoundryException as e:
            logger.error(f"Failed to delete gateway {gateway_id}: {e}")
            # Continue with Redis cleanup even if gateway deletion fails

        # Step 5: Update gateway_config - remove connector
        del gateway_config[connector_id]

        # Step 5b: Update gateway_slugs - remove connector's slug
        gateway_slugs = mcp_tool.get("gateway_slugs", {})
        gateway_slugs.pop(connector_id, None)

        # Step 6: Update server_config - remove connector's tools
        server_config.pop(connector_id, None)

        # Step 7: Update allowed_tools and allowed_tool_names - remove this connector's tools
        allowed_tools = mcp_tool.get("allowed_tools", [])
        updated_allowed_tools = [tool for tool in allowed_tools if tool not in tool_original_names_to_remove]

        allowed_tool_names = mcp_tool.get("allowed_tool_names", [])
        updated_allowed_tool_names = [tool for tool in allowed_tool_names if tool not in tool_names_to_remove]

        # Track virtual server deletion for metadata cleanup later
        virtual_server_deleted = False
        deleted_virtual_server_id = None

        # Step 8: Determine if we should remove entire MCP config or update it
        if not gateway_config:  # No more connectors - complete cleanup
            # Delete virtual server from MCP Foundry
            virtual_server_id = mcp_tool.get("server_url")
            deleted_virtual_server_id = virtual_server_id  # Track for metadata cleanup
            if virtual_server_id:
                try:
                    await mcp_foundry_service.delete_virtual_server(virtual_server_id)
                    virtual_server_deleted = True  # Track successful deletion for metadata cleanup
                    logger.debug(f"Successfully deleted virtual server {virtual_server_id}")
                except MCPFoundryException as e:
                    logger.error(f"Failed to delete virtual server {virtual_server_id}: {e}")
                    # Continue with cleanup

            # Remove entire MCP tool config from tools array
            tools.pop(mcp_tool_index)
            logger.debug("Removed entire MCP tool config (no connectors remaining)")
        else:
            # Update MCP tool config (connectors still remain)
            mcp_tool["gateway_config"] = gateway_config
            mcp_tool["gateway_slugs"] = gateway_slugs
            mcp_tool["server_config"] = server_config
            mcp_tool["allowed_tools"] = updated_allowed_tools
            mcp_tool["allowed_tool_names"] = updated_allowed_tool_names
            tools[mcp_tool_index] = mcp_tool
            logger.debug(f"Updated MCP tool config ({len(gateway_config)} connectors remaining)")

        # Step 9: Save updated config to Redis
        payload = {
            **config_data,
            "prompt_id": budprompt_id,
            "version": target_version,
            "set_default": False,
            "tools": tools,
            "permanent": permanent,  # Control TTL
        }
        await self._save_prompt_config_to_redis(payload)

        # Remove gateway_id from PromptVersion metadata (if prompt and version exist in DB)
        try:
            # Check if prompt exists by name (budprompt_id is the prompt name)
            db_prompt = await PromptDataManager(self.session).retrieve_by_fields(
                PromptModel,
                fields={"name": budprompt_id, "status": PromptStatusEnum.ACTIVE},
                missing_ok=True,
            )

            if db_prompt:
                # Check if prompt_version exists
                db_prompt_version = await PromptVersionDataManager(self.session).retrieve_by_fields(
                    PromptVersionModel,
                    fields={"prompt_id": db_prompt.id, "version": int(target_version)},
                    missing_ok=True,
                )

                if db_prompt_version:
                    # Get existing metadata
                    existing_metadata = (
                        db_prompt_version.version_metadata
                        if isinstance(db_prompt_version.version_metadata, dict)
                        else {}
                    )

                    # Remove gateway_id from gateway_ids array if present
                    if "gateway_ids" in existing_metadata and isinstance(existing_metadata["gateway_ids"], list):
                        gateway_ids = existing_metadata["gateway_ids"]

                        # Remove the gateway_id
                        if gateway_id in gateway_ids:
                            gateway_ids.remove(gateway_id)
                            existing_metadata["gateway_ids"] = gateway_ids

                            # Update the prompt_version record using async pattern
                            self.session.refresh(db_prompt_version)
                            db_prompt_version = await PromptVersionDataManager(self.session).update_by_fields(
                                db_prompt_version, {"version_metadata": existing_metadata}
                            )

                            logger.debug(
                                f"Removed gateway_id {gateway_id} from prompt_version metadata",
                                prompt_id=db_prompt.id,
                                version=target_version,
                            )

                    # Remove virtual_server_id if virtual server was deleted (no connectors remaining)
                    if virtual_server_deleted and deleted_virtual_server_id:
                        if "virtual_server_id" in existing_metadata:
                            # Clear virtual_server_id since virtual server was deleted
                            del existing_metadata["virtual_server_id"]

                            # Update again with cleared virtual_server_id
                            self.session.refresh(db_prompt_version)
                            db_prompt_version = await PromptVersionDataManager(self.session).update_by_fields(
                                db_prompt_version, {"version_metadata": existing_metadata}
                            )

                            logger.debug(
                                f"Removed virtual_server_id {deleted_virtual_server_id} from prompt_version metadata (no connectors remaining)",
                                prompt_id=db_prompt.id,
                                version=target_version,
                            )
        except Exception as e:
            # Silent failure - don't block connector disconnection if DB update fails
            logger.warning(f"Failed to update prompt_version metadata during disconnect: {e}", exc_info=True)

        # Step 10: Return response
        return {
            "prompt_id": budprompt_id,
            "connector_id": connector_id,
            "deleted_gateway_id": gateway_id,
        }

    async def _save_prompt_config_to_redis(self, payload: dict) -> dict:
        """Save prompt configuration to Redis via budprompt service.

        Args:
            payload: Complete payload dictionary to send to budprompt service.
                    Must include: prompt_id, version, tools
                    Optional: set_default, allow_multiple_calls, and any other config fields

        Returns:
            dict: Response data from budprompt service

        Raises:
            ClientException: If save fails
        """
        prompt_config_endpoint = (
            f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_prompt_app_id}/method/v1/prompt/prompt-config"
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(prompt_config_endpoint, json=payload) as response:
                    response_data = await response.json()

                    if response.status != 200:
                        logger.error(f"Failed to save prompt config: {response.status} {response_data}")
                        raise ClientException(
                            message="Failed to save prompt configuration",
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )

                    logger.debug(f"Successfully saved prompt config for {payload.get('prompt_id')}")
                    return response_data

        except aiohttp.ClientError as e:
            logger.exception(f"Network error saving prompt config: {e}")
            raise ClientException(
                message="Unable to save prompt configuration",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    async def _store_mcp_tool_config(
        self,
        budprompt_id: str,
        connector_id: str,
        gateway_id: str,
        gateway_slug: Optional[str] = None,
        version: Optional[int] = None,
        permanent: bool = False,
    ) -> None:
        """Store MCP tool configuration in Redis via budprompt service.

        Args:
            budprompt_id: The bud prompt ID (can be UUID or draft prompt ID)
            connector_id: The connector ID
            gateway_id: The gateway ID from MCP Foundry
            gateway_slug: The gateway slug from MCP Foundry (used for tool name shortening)
            version: Optional version to update. If None, updates default version
            permanent: Store configuration permanently without expiration

        Raises:
            ClientException: If storing configuration fails
        """
        # 1. Create MCPToolConfig using Pydantic schema
        gateway_slugs = {connector_id: gateway_slug} if gateway_slug else {}
        mcp_tool = MCPToolConfig(
            type="mcp",
            server_label=None,
            server_description=None,
            server_url=None,
            require_approval="never",
            allowed_tools=[],
            connector_id=None,  # Set to None as requested
            gateway_config={connector_id: gateway_id},
            gateway_slugs=gateway_slugs,
        )
        mcp_tool_dict = mcp_tool.model_dump(exclude_none=True)

        # 2. Fetch existing prompt configuration
        config_exists = True
        existing_config_data = {}

        try:
            config_response = await self._perform_get_prompt_config_request(
                budprompt_id,
                version=version,  # Use provided version or None for default
                raw_data=True,
            )
            config_data = config_response.get("data", {})
            existing_tools = config_data.get("tools", [])

            # Store the entire existing config data to preserve it
            existing_config_data = config_data

            # Determine the version to use
            target_version = config_response.get("version", 1) if version is None else version

        except ClientException as e:
            if e.status_code == 404:
                # No existing config
                config_exists = False
                existing_tools = []
                target_version = version if version else 1  # Default to 1 if not specified
            else:
                raise

        # 3. Check if an MCP tool config already exists and merge or create new
        existing_mcp_tool_index = None
        existing_mcp_tool = None

        for index, tool in enumerate(existing_tools):
            if tool.get("type") == "mcp":
                existing_mcp_tool = tool
                existing_mcp_tool_index = index
                break

        # 4. Handle merging or creating MCP tool config
        if existing_mcp_tool:
            # MCP tool exists - check for duplicate connector
            gateway_config = existing_mcp_tool.get("gateway_config", {})
            if connector_id in gateway_config:
                logger.error(f"Connector {connector_id} already exists in prompt config")
                raise ClientException(
                    message="Connector is already registered for prompt.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Merge new connector into existing MCP tool config
            gateway_config[connector_id] = gateway_id
            existing_mcp_tool["gateway_config"] = gateway_config

            # Also merge gateway_slugs for tool name shortening
            gateway_slugs_dict = existing_mcp_tool.get("gateway_slugs", {})
            if gateway_slug:
                gateway_slugs_dict[connector_id] = gateway_slug
            existing_mcp_tool["gateway_slugs"] = gateway_slugs_dict

            # Also update server_config to maintain consistency
            server_config = existing_mcp_tool.get("server_config", {})
            # Note: server_config is updated separately when tools are added
            existing_mcp_tool["server_config"] = server_config

            # Update the existing tool in the array
            existing_tools[existing_mcp_tool_index] = existing_mcp_tool
            updated_tools = existing_tools

            logger.debug(f"Merged connector {connector_id} into existing MCP tool config")
        else:
            # No MCP tool exists - create new entry
            updated_tools = existing_tools + [mcp_tool_dict]
            logger.debug(f"Created new MCP tool config with connector {connector_id}")

        # 5. Save updated config
        if config_exists:
            # Preserve all existing config data, only update tools field
            payload = {
                **existing_config_data,  # Spread all existing fields
                "prompt_id": budprompt_id,
                "version": target_version,
                "set_default": False,  # Don't change default for existing configs
                "tools": updated_tools,  # Override tools field
                "permanent": permanent,  # Control TTL
            }
        else:
            # New config: set allow_multiple_calls=true for MCP support
            payload = {
                "prompt_id": budprompt_id,
                "version": target_version,
                "set_default": True,  # Set as default for new configs
                "allow_multiple_calls": True,  # Enable for MCP tools
                "tools": updated_tools,
                "permanent": permanent,  # Control TTL
            }

        await self._save_prompt_config_to_redis(payload)
        logger.debug(f"Successfully stored MCP tool config for connector {connector_id}")

    async def get_tools(
        self,
        prompt_id: str,
        connector_id: str,
        version: Optional[int] = None,
        offset: int = 0,
        limit: int = 10,
        filters: dict = {},
        order_by: list = [],
        search: bool = False,
    ) -> tuple[list[ToolListItem], int]:
        """Get tools list from MCP Foundry for a specific prompt and connector.

        Args:
            prompt_id: Prompt ID (UUID or draft ID)
            connector_id: Connector ID to get tools for
            version: Optional version of prompt config
            offset: Pagination offset
            limit: Pagination limit
            filters: Additional filters
            order_by: Ordering fields
            search: Enable search

        Returns:
            Tuple of (list of tools, total count)
        """
        logger.debug(f"Fetching tools for prompt_id={prompt_id}, connector_id={connector_id}, version={version}")

        # 1. Fetch prompt config from Redis
        try:
            config_response = await self._perform_get_prompt_config_request(prompt_id, version=version, raw_data=True)
            config_data = config_response.get("data", {})
            tools = config_data.get("tools", [])
        except ClientException as e:
            if e.status_code == 404:
                # Prompt config not found - return empty
                logger.debug(f"Prompt config not found for {prompt_id}")
                return [], 0
            raise

        # 2. Find gateway_id and added tool IDs from gateway_config and server_config
        gateway_id = None
        added_tool_ids = []
        for tool in tools:
            if tool.get("type") == "mcp":
                gateway_config = tool.get("gateway_config", {})
                if connector_id in gateway_config:
                    gateway_id = gateway_config[connector_id]
                    # Extract added tool IDs from server_config
                    server_config = tool.get("server_config", {})
                    added_tool_ids = server_config.get(connector_id, [])
                    break

        if not gateway_id:
            # Connector not registered for this prompt
            logger.debug(f"Connector {connector_id} not found in prompt {prompt_id}")
            return [], 0

        logger.debug(f"Found gateway_id={gateway_id} for connector={connector_id}, added_tool_ids={added_tool_ids}")

        # 3. Fetch gateway with all tools from MCP Foundry
        try:
            gateway_data = await mcp_foundry_service.get_gateway_by_id(gateway_id)
            all_tools = gateway_data.get("tools", [])

            logger.debug(f"Successfully fetched gateway {gateway_id} with {len(all_tools)} tools from MCP Foundry")

            # Apply pagination in-memory
            total_count = len(all_tools)
            mcp_foundry_response = all_tools[offset : offset + limit]

        except MCPFoundryException as e:
            logger.error(f"MCP Foundry API error: {e}")
            return [], 0
        except Exception as e:
            logger.error(f"Unexpected error calling MCP Foundry: {e}")
            return [], 0

        # 4. Parse MCP Foundry response to ToolListItem
        tool_items = []
        for item in mcp_foundry_response:
            try:
                tool_id = item.get("id", "")
                is_added = tool_id in added_tool_ids
                tool_item = ToolListItem(
                    id=UUID(tool_id),
                    name=item.get("displayName", ""),
                    type=item.get("originalName", ""),
                    is_added=is_added,
                )
                tool_items.append(tool_item)
            except (ValueError, KeyError) as e:
                logger.error(f"Invalid tool item: {e}")
                continue

        logger.debug(f"Returning {len(tool_items)} tools out of {total_count} total")

        return tool_items, total_count

    async def get_tool_by_id(self, tool_id: UUID) -> Tool:
        """Get a single tool by ID from MCP Foundry.

        Args:
            tool_id: Tool ID to retrieve

        Returns:
            Tool object with complete details

        Raises:
            ClientException: If tool not found or request fails
        """
        logger.debug(f"Getting tool with ID: {tool_id}")

        # Fetch from MCP Foundry
        try:
            mcp_foundry_response = await mcp_foundry_service.get_tool_by_id(tool_id)
            logger.debug(f"Successfully fetched tool from MCP Foundry: {tool_id}")

        except MCPFoundryException as e:
            logger.error(f"MCP Foundry API error for tool {tool_id}: {e}")
            raise ClientException(message="Tool not found", status_code=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error getting tool {tool_id}: {e}")
            raise ClientException(message="Tool not found", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Parse MCP response to Tool format
        try:
            tool = Tool(
                id=UUID(mcp_foundry_response.get("id", str(tool_id))),
                name=mcp_foundry_response.get("displayName", "Unknown Tool"),
                description=mcp_foundry_response.get("description", ""),
                type=mcp_foundry_response.get("originalName", "unknown"),
                schema=mcp_foundry_response.get("inputSchema", {}),
            )

            logger.debug(f"Successfully retrieved tool: {tool.name} with ID: {tool_id}")
            return tool

        except (ValueError, KeyError) as e:
            logger.error(f"Failed to parse tool response for {tool_id}: {e}")
            raise ClientException(
                message="Invalid tool data found",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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

    async def _perform_cleanup_request(self, prompt_ids: List, debug: bool = False) -> Dict[str, Any]:
        """Perform cleanup request to budprompt service via Dapr.

        Args:
            prompt_ids: List of prompt cleanup items with prompt_id and version
            debug: If True, runs cleanup synchronously. If False, runs via Dapr workflow (default)

        Returns:
            Response data from budprompt service

        Raises:
            ClientException: If request fails
        """
        cleanup_endpoint = f"{app_settings.dapr_base_url}/v1.0/invoke/{app_settings.bud_prompt_app_id}/method/v1/prompt/prompt-cleanup"

        # Prepare payload with prompts list
        payload = {"prompts": prompt_ids, "debug": debug}

        logger.debug(f"Performing cleanup request to budprompt: {payload}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(cleanup_endpoint, json=payload) as response:
                    response_data = await response.json()

                    if response.status != 200:
                        logger.error(f"Failed to cleanup prompts: {response.status} {response_data}")
                        raise ClientException(
                            message=response_data.get("message", "Failed to cleanup prompts"),
                            status_code=response.status,
                        )

                    logger.debug(f"Successfully cleaned up {len(prompt_ids)} prompts")
                    return response_data

        except aiohttp.ClientError as e:
            logger.exception(f"Network error during cleanup request: {e}")
            raise ClientException(
                message="Network error while cleaning up prompts",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from e
        except ClientException:
            raise
        except Exception as e:
            logger.exception(f"Failed to cleanup prompts: {e}")
            raise ClientException(
                message="Failed to cleanup prompts",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def initiate_oauth_for_connector(
        self,
        prompt_id: str,
        connector_id: str,
        version: Optional[int] = 1,
    ) -> Dict[str, Any]:
        """Initiate OAuth flow for a connector.

        Args:
            prompt_id: The prompt ID (UUID or draft ID)
            connector_id: The connector ID
            version: Version of prompt config (defaults to 1)

        Returns:
            Dict containing OAuth initiation response from MCP Foundry

        Raises:
            ClientException: If prompt config not found or OAuth initiation fails
        """
        logger.debug(f"Initiating OAuth for connector {connector_id} in prompt {prompt_id} version {version}")

        try:
            # 1. Fetch prompt config from Redis
            config_response = await self._perform_get_prompt_config_request(prompt_id, version=version, raw_data=True)
            config_data = config_response.get("data", {})
            tools = config_data.get("tools", [])

            # 2. Find MCP tool and extract gateway_config
            mcp_tool = None
            for tool in tools:
                if tool.get("type") == "mcp":
                    mcp_tool = tool
                    break

            if not mcp_tool:
                raise ClientException(
                    message=f"No MCP connectors registered for prompt {prompt_id}",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            # 3. Extract gateway_config from MCP tool
            gateway_config = mcp_tool.get("gateway_config", {})

            # 4. Find gateway_id for the connector
            gateway_id = gateway_config.get(connector_id)

            if not gateway_id:
                raise ClientException(
                    message=f"Connector {connector_id} not registered for prompt {prompt_id} version {version}",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            logger.debug(f"Found gateway_id {gateway_id} for connector {connector_id}")

            # 5. Call MCP Foundry to initiate OAuth
            oauth_response = await mcp_foundry_service.initiate_oauth(gateway_id)

            logger.debug(f"OAuth flow initiated successfully for gateway {gateway_id}")
            return oauth_response

        except ClientException:
            raise
        except MCPFoundryException as e:
            logger.error(f"MCP Foundry error initiating OAuth: {e}")
            raise ClientException(
                message="Failed to initiate OAuth flow",
                status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error initiating OAuth: {e}")
            raise ClientException(
                message="Failed to initiate OAuth flow",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    async def get_oauth_status_for_connector(
        self,
        prompt_id: str,
        connector_id: str,
        version: Optional[int] = 1,
    ) -> Dict[str, Any]:
        """Get OAuth status for a connector.

        Args:
            prompt_id: The prompt ID (UUID or draft ID)
            connector_id: The connector ID
            version: Version of prompt config (defaults to 1)

        Returns:
            Dict containing OAuth status from MCP Foundry

        Raises:
            ClientException: If prompt config not found or OAuth status check fails
        """
        logger.debug(f"Getting OAuth status for connector {connector_id} in prompt {prompt_id} version {version}")

        try:
            # 1. Fetch prompt config from Redis
            config_response = await self._perform_get_prompt_config_request(prompt_id, version=version, raw_data=True)
            config_data = config_response.get("data", {})
            tools = config_data.get("tools", [])

            # 2. Find MCP tool and extract gateway_config
            mcp_tool = next((tool for tool in tools if tool.get("type") == "mcp"), None)

            if not mcp_tool:
                raise ClientException(
                    message=f"No MCP connectors registered for prompt {prompt_id}",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            # 3. Extract gateway_config from MCP tool
            gateway_config = mcp_tool.get("gateway_config", {})

            # 4. Find gateway_id for the connector
            gateway_id = gateway_config.get(connector_id)

            if not gateway_id:
                raise ClientException(
                    message=f"Connector {connector_id} not registered for prompt {prompt_id} version {version}",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            logger.debug(f"Found gateway_id {gateway_id} for connector {connector_id}")

            # 5. Call MCP Foundry to get OAuth status
            oauth_status = await mcp_foundry_service.get_oauth_status(gateway_id)

            logger.debug(f"OAuth status retrieved successfully for gateway {gateway_id}")
            return oauth_status

        except ClientException:
            raise
        except MCPFoundryException as e:
            logger.error(f"MCP Foundry error getting OAuth status: {e}")
            raise ClientException(
                message="Failed to get OAuth status",
                status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error(f"Unexpected error getting OAuth status: {e}")
            raise ClientException(
                message="Failed to get OAuth status",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def fetch_tools_after_oauth_for_connector(
        self,
        prompt_id: str,
        connector_id: str,
        version: Optional[int] = 1,
    ) -> Dict[str, Any]:
        """Fetch tools after OAuth for a connector.

        Args:
            prompt_id: The prompt ID (UUID or draft ID)
            connector_id: The connector ID
            version: Version of prompt config (defaults to 1)

        Returns:
            Dict containing tool fetching response from MCP Foundry

        Raises:
            ClientException: If prompt config not found or tool fetching fails
        """
        logger.debug(f"Fetching tools for connector {connector_id} in prompt {prompt_id} version {version}")

        try:
            # 1. Fetch prompt config from Redis
            config_response = await self._perform_get_prompt_config_request(prompt_id, version=version, raw_data=True)
            config_data = config_response.get("data", {})
            tools = config_data.get("tools", [])

            # 2. Find MCP tool and extract gateway_config
            mcp_tool = next((tool for tool in tools if tool.get("type") == "mcp"), None)

            if not mcp_tool:
                raise ClientException(
                    message=f"No MCP connectors registered for prompt {prompt_id}",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            # 3. Extract gateway_config from MCP tool
            gateway_config = mcp_tool.get("gateway_config", {})

            # 4. Find gateway_id for the connector
            gateway_id = gateway_config.get(connector_id)

            if not gateway_id:
                raise ClientException(
                    message=f"Connector {connector_id} not registered for prompt {prompt_id} version {version}",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            logger.debug(f"Found gateway_id {gateway_id} for connector {connector_id}")

            # 5. Call MCP Foundry to fetch tools
            fetch_response = await mcp_foundry_service.fetch_tools_after_oauth(gateway_id)

            logger.debug(f"Tools fetched successfully for gateway {gateway_id}")
            return fetch_response

        except ClientException:
            # Re-raise client exceptions as-is
            raise
        except Exception as e:
            logger.error(f"Error fetching tools for connector {connector_id}: {e}", exc_info=True)
            raise ClientException(
                message="Failed to fetch tools after OAuth",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

    async def handle_oauth_callback(self, code: str, state: str) -> Dict[str, Any]:
        """Handle OAuth callback.

        Args:
            code: Authorization code from OAuth provider
            state: State parameter from OAuth flow

        Returns:
            Dict containing callback response from MCP Foundry

        Raises:
            ClientException: If OAuth callback fails
        """
        logger.debug("Handling OAuth callback")

        try:
            # Forward to MCP Foundry
            callback_response = await mcp_foundry_service.handle_oauth_callback(code, state)

            logger.debug("OAuth callback handled successfully")
            return callback_response

        except MCPFoundryException as e:
            logger.error(f"MCP Foundry OAuth callback failed: {e}")
            raise ClientException(
                message="Failed to handle OAuth callback",
                status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error handling OAuth callback: {e}", exc_info=True)
            raise ClientException(
                message="Failed to handle OAuth callback",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from e

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
            discarded_prompt_ids=request.discarded_prompt_ids,
            client_metadata=request.client_metadata,
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
                "discarded_prompt_ids",
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

            # Extract metadata from budprompt config for version_metadata
            metadata = {}
            if merged_data.get("name"):
                try:
                    prompt_service = PromptService(self.session)
                    config_response = await prompt_service._perform_get_prompt_config_request(
                        prompt_id=merged_data.get("name"),
                        version=1,
                        raw_data=True,
                    )

                    tools = config_response.get("data", {}).get("tools", [])
                    for tool in tools:
                        if tool.get("type") == "mcp":
                            # Extract gateway_ids from gateway_config
                            gateway_config = tool.get("gateway_config", {})
                            if gateway_config:
                                metadata["gateway_ids"] = list(gateway_config.values())

                            # Extract virtual_server_id from server_url
                            virtual_server_id = tool.get("server_url")
                            if virtual_server_id:
                                metadata["virtual_server_id"] = virtual_server_id
                            break

                    if metadata:
                        logger.debug(
                            f"Extracted metadata from budprompt config: {len(metadata.get('gateway_ids', []))} gateway_ids, "
                            f"virtual_server_id={metadata.get('virtual_server_id')}"
                        )
                except Exception as e:
                    logger.warning(f"Failed to extract metadata from budprompt config: {e}")
                    metadata = {}

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
                    version_metadata=metadata,  # Populate with gateway_ids and virtual_server_id from budprompt config
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

            # Cleanup discarded prompt resources
            discarded_prompt_ids = merged_data.get("discarded_prompt_ids", [])
            if discarded_prompt_ids and len(discarded_prompt_ids) > 0:
                try:
                    logger.debug(f"Triggering cleanup for {len(discarded_prompt_ids)} discarded prompts")
                    prompt_service = PromptService(self.session)
                    await prompt_service._perform_cleanup_request(discarded_prompt_ids)
                    logger.debug("Cleanup completed successfully")
                except Exception as e:
                    # Log error but don't fail prompt creation
                    logger.error(
                        f"Failed to cleanup discarded prompts, but prompt creation succeeded: {e}",
                        exc_info=True,
                    )

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
            permanent=request.permanent,
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
                "permanent",
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
            "permanent": data.get("permanent", False),
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

        # Save draft prompt reference for playground access
        try:
            # Get user_id from workflow's created_by field
            user_id = db_workflow.created_by

            if user_id and prompt_id:
                redis_service = RedisService()
                draft_key = f"draft_prompt:{user_id}:{prompt_id}"
                draft_value = json.dumps(
                    {
                        "prompt_id": prompt_id,
                        "user_id": str(user_id),
                    }
                )
                # Set TTL to 24 hours (86400 seconds) - matching budprompt temporary storage
                await redis_service.set(draft_key, draft_value, ex=app_settings.prompt_config_redis_ttl)
        except Exception as e:
            logger.error(f"Failed to cache draft prompt: {e}")
            # Don't fail the notification handler

        # Add prompt to proxy cache for routing
        try:
            await self.add_prompt_to_proxy_cache(prompt_id, prompt_id, ex=app_settings.prompt_config_redis_ttl)
            logger.debug(f"Added prompt {prompt_id} to proxy cache")
        except Exception as e:
            logger.error(f"Failed to add prompt to proxy cache: {e}")
            # Continue - cache update is non-critical

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

    async def add_prompt_to_proxy_cache(
        self, prompt_id: Union[UUID, str], prompt_name: str, ex: Optional[int] = None
    ) -> None:
        """Add prompt to proxy cache for routing through budgateway.

        Args:
            prompt_id: The prompt UUID (can be UUID object or string)
            prompt_name: The prompt name to use as model_name (for draft prompts, same as prompt_id)
        """
        try:
            prompt_key_name = f"prompt:{prompt_name}"
            # Create BudPromptConfig for the provider
            prompt_config = BudPromptConfig(
                type="budprompt",
                api_base=app_settings.bud_prompt_service_url,
                model_name=prompt_key_name,
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
                f"model_table:{prompt_id}",
                json.dumps({str(prompt_id): model_config.model_dump(exclude_none=True)}),
                ex=ex,
            )
            logger.debug(f"Added prompt {prompt_name} to proxy cache with key model_table:{prompt_id}")

        except Exception as e:
            logger.error(f"Failed to add prompt to proxy cache: {e}")
            # Don't raise - cache update is non-critical


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

        # Extract metadata from budprompt config for version_metadata
        metadata = {}
        try:
            prompt_service = PromptService(self.session)
            config_response = await prompt_service._perform_get_prompt_config_request(
                prompt_id=db_prompt.name,
                version=next_version,
                raw_data=True,
            )

            tools = config_response.get("data", {}).get("tools", [])
            for tool in tools:
                if tool.get("type") == "mcp":
                    # Extract gateway_ids from gateway_config
                    gateway_config = tool.get("gateway_config", {})
                    if gateway_config:
                        metadata["gateway_ids"] = list(gateway_config.values())

                    # Extract virtual_server_id from server_url
                    virtual_server_id = tool.get("server_url")
                    if virtual_server_id:
                        metadata["virtual_server_id"] = virtual_server_id
                    break

            if metadata:
                logger.debug(
                    f"Extracted metadata from budprompt config for version {next_version}: "
                    f"{len(metadata.get('gateway_ids', []))} gateway_ids, "
                    f"virtual_server_id={metadata.get('virtual_server_id')}"
                )
        except Exception as e:
            logger.warning(f"Failed to extract metadata from budprompt config: {e}")
            metadata = {}

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
                version_metadata=metadata,  # Populate with gateway_ids and virtual_server_id from budprompt config
            )
        )

        # If set_as_default is True, update the prompt's default_version_id
        if set_as_default:
            await PromptDataManager(self.session).update_by_fields(db_prompt, {"default_version_id": db_version.id})
            # Reload the prompt to get the updated default_version
            self.session.refresh(db_prompt)
            # Update API key cache for the project with new default version
            try:
                await CredentialService(self.session).update_proxy_cache(db_prompt.project_id)
                logger.debug(f"Updated credential proxy cache for project {db_prompt.project_id}")
            except Exception as e:
                logger.error(f"Failed to update credential proxy cache: {e}")
                # Continue - cache update is non-critical

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
            # Update API key cache for the project with new default version
            try:
                await CredentialService(self.session).update_proxy_cache(db_prompt.project_id)
                logger.debug(f"Updated credential proxy cache for project {db_prompt.project_id}")
            except Exception as e:
                logger.error(f"Failed to update credential proxy cache: {e}")
                # Continue - cache update is non-critical

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

        # Delete MCP Foundry gateways if present in version metadata
        if db_version.version_metadata and isinstance(db_version.version_metadata, dict):
            gateway_ids = db_version.version_metadata.get("gateway_ids", [])

            if gateway_ids:
                logger.debug(
                    f"Deleting {len(gateway_ids)} MCP Foundry gateways for version {version_id}",
                    gateway_ids=gateway_ids,
                )

                for gateway_id in gateway_ids:
                    # delete_gateway already handles 404 gracefully, so we can call directly
                    # Any other errors will be raised and propagated
                    await mcp_foundry_service.delete_gateway(gateway_id)
                    logger.debug(f"Successfully deleted MCP Foundry gateway {gateway_id}")

        # Delete virtual server if present in version metadata
        if db_version.version_metadata and isinstance(db_version.version_metadata, dict):
            virtual_server_id = db_version.version_metadata.get("virtual_server_id")

            if virtual_server_id:
                logger.debug(
                    f"Deleting virtual server {virtual_server_id} for version {version_id}",
                )

                try:
                    # delete_virtual_server handles 404 gracefully (returns empty dict)
                    await mcp_foundry_service.delete_virtual_server(virtual_server_id)
                    logger.debug(f"Successfully deleted virtual server {virtual_server_id}")
                except MCPFoundryException as e:
                    # Log error but continue - don't block version deletion
                    logger.error(f"Failed to delete virtual server {virtual_server_id}: {e}")

        # Soft delete the version by updating its status
        await PromptVersionDataManager(self.session).update_by_fields(
            db_version, {"status": PromptVersionStatusEnum.DELETED}
        )

        # Update credential proxy cache to remove the deleted version's entry
        # This ensures the gateway cache no longer contains prompt:{name}:v{version} for the deleted version
        try:
            await CredentialService(self.session).update_proxy_cache(db_prompt.project_id)
            logger.debug(f"Updated credential proxy cache for project {db_prompt.project_id}")
        except Exception as e:
            logger.error(f"Failed to update credential proxy cache: {e}")
            # Continue - cache cleanup is non-critical

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
