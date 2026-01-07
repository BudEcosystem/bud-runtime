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

"""Business logic services for the tool operations module."""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import status

from ..commons import logging
from ..commons.constants import (
    APP_ICONS,
    WorkflowStatusEnum,
    WorkflowTypeEnum,
)
from ..commons.db_utils import SessionMixin
from ..commons.exceptions import ClientException, MCPFoundryException
from ..shared.mcp_foundry_service import mcp_foundry_service
from ..workflow_ops.crud import WorkflowDataManager, WorkflowStepDataManager
from ..workflow_ops.models import Workflow as WorkflowModel
from ..workflow_ops.models import WorkflowStep as WorkflowStepModel
from ..workflow_ops.schemas import WorkflowUtilCreate
from ..workflow_ops.services import WorkflowService
from .schemas import (
    CatalogueServerRead,
    CreateToolWorkflowRequest,
    ToolCreationWorkflowStepData,
    ToolRead,
    ToolSourceType,
    ToolUpdate,
    VirtualServerRead,
    VirtualServerUpdateRequest,
)


logger = logging.get_logger(__name__)


class ToolService(SessionMixin):
    """Service for managing tools via MCP Foundry proxy."""

    def _transform_tool_response(self, mcp_tool: Dict[str, Any]) -> ToolRead:
        """Transform MCP Foundry tool response to ToolRead schema.

        Args:
            mcp_tool: Raw tool data from MCP Foundry (camelCase keys)

        Returns:
            ToolRead: Transformed tool data with snake_case keys
        """
        return ToolRead(
            id=str(mcp_tool.get("id", "")),
            name=mcp_tool.get("originalName", mcp_tool.get("name", "")),
            display_name=mcp_tool.get("displayName"),
            custom_name=mcp_tool.get("customName"),
            url=mcp_tool.get("url"),
            description=mcp_tool.get("description"),
            integration_type=mcp_tool.get("integrationType"),
            request_type=mcp_tool.get("requestType"),
            headers=mcp_tool.get("headers"),
            input_schema=mcp_tool.get("inputSchema"),
            output_schema=mcp_tool.get("outputSchema"),
            annotations=mcp_tool.get("annotations"),
            is_active=mcp_tool.get("isActive", True),
            enabled=mcp_tool.get("enabled", True),
            reachable=mcp_tool.get("reachable", True),
            visibility=mcp_tool.get("visibility"),
            tags=mcp_tool.get("tags"),
            team_id=mcp_tool.get("teamId"),
            server_id=mcp_tool.get("serverId"),
            gateway_id=mcp_tool.get("gatewayId"),
            auth=mcp_tool.get("auth"),
            metrics=mcp_tool.get("metrics"),
            created_at=mcp_tool.get("createdAt"),
            updated_at=mcp_tool.get("updatedAt"),
        )

    def _transform_update_to_mcp_format(self, update_data: ToolUpdate) -> Dict[str, Any]:
        """Transform ToolUpdate schema to MCP Foundry format (camelCase).

        Args:
            update_data: Update data with snake_case keys

        Returns:
            Dict with camelCase keys for MCP Foundry API
        """
        result: Dict[str, Any] = {}

        field_mapping = {
            "name": "name",
            "display_name": "displayName",
            "custom_name": "customName",
            "url": "url",
            "description": "description",
            "integration_type": "integrationType",
            "request_type": "requestType",
            "headers": "headers",
            "input_schema": "inputSchema",
            "output_schema": "outputSchema",
            "is_active": "isActive",
            "visibility": "visibility",
            "tags": "tags",
        }

        data = update_data.model_dump(exclude_none=True)
        for snake_key, camel_key in field_mapping.items():
            if snake_key in data:
                result[camel_key] = data[snake_key]

        return result

    async def list_tools(
        self,
        cursor: Optional[str] = None,
        include_inactive: bool = False,
        tags: Optional[List[str]] = None,
        team_id: Optional[str] = None,
        visibility: Optional[str] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> Tuple[List[ToolRead], int, Optional[str]]:
        """List tools from MCP Foundry with filtering.

        Args:
            cursor: Pagination cursor for next page
            include_inactive: Include inactive tools
            tags: Filter by tags
            team_id: Filter by team ID
            visibility: Filter by visibility
            offset: Number of items to skip (used if cursor not provided)
            limit: Maximum number of items to return

        Returns:
            Tuple of (list of tools, total count, next cursor)

        Raises:
            ClientException: If the request fails
        """
        try:
            logger.info(
                "Fetching tools from MCP Foundry",
                cursor=cursor,
                include_inactive=include_inactive,
                tags=tags,
                team_id=team_id,
                visibility=visibility,
            )

            response = await mcp_foundry_service.list_all_tools(
                cursor=cursor,
                include_inactive=include_inactive,
                tags=tags,
                team_id=team_id,
                visibility=visibility,
            )

            # Handle response structure
            if isinstance(response, dict):
                tools_data = response.get("data", response.get("tools", []))
                next_cursor = response.get("next_cursor", response.get("nextCursor"))
            else:
                tools_data = response if isinstance(response, list) else []
                next_cursor = None

            # Apply offset/limit if no cursor-based pagination
            if cursor is None and tools_data:
                tools_data = tools_data[offset : offset + limit]

            # Transform to ToolRead schemas
            tools = [self._transform_tool_response(tool) for tool in tools_data]

            # Total count (MCP Foundry may not provide this)
            total_count = len(tools_data) if cursor is None else 0

            logger.debug(
                "Successfully fetched tools from MCP Foundry",
                count=len(tools),
            )

            return tools, total_count, next_cursor

        except MCPFoundryException as e:
            logger.error(f"MCP Foundry error listing tools: {e.message}")
            raise ClientException(
                message=e.message,
                status_code=e.status_code,
            )
        except Exception as e:
            error_msg = f"Unexpected error listing tools: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ClientException(
                message="Failed to list tools",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    async def get_tool(self, tool_id: str) -> ToolRead:
        """Get a single tool by ID.

        Args:
            tool_id: The ID of the tool to retrieve

        Returns:
            ToolRead schema with tool details

        Raises:
            ClientException: If tool not found or other error
        """
        try:
            logger.debug(f"Fetching tool {tool_id} from MCP Foundry")

            response = await mcp_foundry_service.get_tool_by_id(tool_id)
            tool = self._transform_tool_response(response)

            logger.debug(f"Successfully fetched tool {tool_id}")
            return tool

        except MCPFoundryException as e:
            if e.status_code == 404:
                raise ClientException(
                    message=f"Tool {tool_id} not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            raise ClientException(
                message=e.message,
                status_code=e.status_code,
            )
        except Exception as e:
            error_msg = f"Unexpected error getting tool {tool_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ClientException(
                message="Failed to get tool",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    async def update_tool(self, tool_id: str, update_data: ToolUpdate) -> ToolRead:
        """Update a tool's properties.

        Args:
            tool_id: The ID of the tool to update
            update_data: Fields to update

        Returns:
            ToolRead schema with updated tool details

        Raises:
            ClientException: If tool not found or update fails
        """
        try:
            logger.debug(
                f"Updating tool {tool_id} in MCP Foundry",
                update_fields=list(update_data.model_dump(exclude_none=True).keys()),
            )

            # Transform to MCP Foundry format
            mcp_update_data = self._transform_update_to_mcp_format(update_data)

            response = await mcp_foundry_service.update_tool(tool_id, mcp_update_data)
            tool = self._transform_tool_response(response)

            logger.debug(f"Successfully updated tool {tool_id}")
            return tool

        except MCPFoundryException as e:
            if e.status_code == 404:
                raise ClientException(
                    message=f"Tool {tool_id} not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            raise ClientException(
                message=e.message,
                status_code=e.status_code,
            )
        except Exception as e:
            error_msg = f"Unexpected error updating tool {tool_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ClientException(
                message="Failed to update tool",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    async def delete_tool(self, tool_id: str) -> None:
        """Delete a tool.

        Args:
            tool_id: The ID of the tool to delete

        Raises:
            ClientException: If tool not found or deletion fails
        """
        try:
            logger.debug(f"Deleting tool {tool_id} from MCP Foundry")

            await mcp_foundry_service.delete_tool(tool_id)

            logger.debug(f"Successfully deleted tool {tool_id}")

        except MCPFoundryException as e:
            if e.status_code == 404:
                raise ClientException(
                    message=f"Tool {tool_id} not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            raise ClientException(
                message=e.message,
                status_code=e.status_code,
            )
        except Exception as e:
            error_msg = f"Unexpected error deleting tool {tool_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ClientException(
                message="Failed to delete tool",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ToolCreationWorkflowService(SessionMixin):
    """Service for managing tool creation workflows.

    Uses database state tracking (Workflow + WorkflowStep tables) similar to
    LocalModelWorkflowService. Does NOT use Dapr workflows - those are for
    background scheduled tasks only.
    """

    async def add_tool_workflow(
        self,
        current_user_id: UUID,
        request: CreateToolWorkflowRequest,
    ) -> WorkflowModel:
        """Create or update a tool creation workflow step.

        Args:
            current_user_id: The ID of the current user
            request: The workflow request data

        Returns:
            WorkflowModel: The workflow database record

        Raises:
            ClientException: If validation fails
        """
        step_number = request.step_number
        workflow_id = request.workflow_id
        workflow_total_steps = request.workflow_total_steps
        trigger_workflow = request.trigger_workflow

        logger.info(
            "Processing tool creation workflow",
            workflow_id=str(workflow_id) if workflow_id else "new",
            step_number=step_number,
            trigger_workflow=trigger_workflow,
        )

        # Retrieve or create workflow
        workflow_create = WorkflowUtilCreate(
            workflow_type=WorkflowTypeEnum.TOOL_CREATION,
            title="Tool Creation",
            total_steps=workflow_total_steps,
            icon=APP_ICONS["general"]["tools"],
            tag="Tool Creation",
        )
        db_workflow = await WorkflowService(self.session).retrieve_or_create_workflow(
            workflow_id, workflow_create, current_user_id
        )

        # Prepare workflow step data
        workflow_step_data = ToolCreationWorkflowStepData(
            source_type=request.source_type,
            openapi_url=request.openapi_url,
            api_docs_url=request.api_docs_url,
            enhance_with_ai=request.enhance_with_ai,
            catalogue_server_ids=request.catalogue_server_ids,
            selected_tool_ids=request.selected_tool_ids,
            virtual_server_name=request.virtual_server_name,
        ).model_dump(exclude_none=True, exclude_unset=True, mode="json")

        # Get existing workflow steps
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": db_workflow.id}
        )

        # Find current step if exists
        db_current_workflow_step = None
        if db_workflow_steps:
            for db_step in db_workflow_steps:
                if db_step.step_number == step_number:
                    db_current_workflow_step = db_step
                    break

        if db_current_workflow_step:
            logger.info(f"Workflow {db_workflow.id} step {step_number} already exists, updating")

            # Merge existing data with new data
            existing_data = db_current_workflow_step.data or {}
            merged_data = {**existing_data, **workflow_step_data}

            await WorkflowStepDataManager(self.session).update_by_fields(
                db_current_workflow_step,
                {"data": merged_data},
            )
        else:
            logger.info(f"Creating workflow step {step_number} for workflow {db_workflow.id}")

            await WorkflowStepDataManager(self.session).insert_one(
                WorkflowStepModel(
                    workflow_id=db_workflow.id,
                    step_number=step_number,
                    data=workflow_step_data,
                )
            )

        # Update workflow current step
        db_max_step_number = max(step.step_number for step in db_workflow_steps) if db_workflow_steps else 0
        workflow_current_step = max(step_number, db_max_step_number)

        db_workflow = await WorkflowDataManager(self.session).update_by_fields(
            db_workflow,
            {"current_step": workflow_current_step},
        )

        # Trigger tool creation if requested
        if trigger_workflow:
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": db_workflow.id}
            )

            # Collect all step data
            combined_data: Dict[str, Any] = {}
            for db_step in db_workflow_steps:
                if db_step.data:
                    combined_data.update(db_step.data)

            await self._execute_tool_creation(
                current_user_id=current_user_id,
                workflow=db_workflow,
                step_data=combined_data,
            )

        return db_workflow

    async def _execute_tool_creation(
        self,
        current_user_id: UUID,
        workflow: WorkflowModel,
        step_data: Dict[str, Any],
    ) -> None:
        """Execute the actual tool creation via MCP Foundry.

        Args:
            current_user_id: The ID of the current user
            workflow: The workflow database record
            step_data: Combined step data from all workflow steps
        """
        source_type_str = step_data.get("source_type")
        source_type = ToolSourceType(source_type_str) if source_type_str else None

        logger.info(
            "Executing tool creation",
            workflow_id=str(workflow.id),
            source_type=source_type_str,
        )

        # Update workflow status to in_progress
        await WorkflowDataManager(self.session).update_by_fields(
            workflow,
            {"status": WorkflowStatusEnum.IN_PROGRESS},
        )

        try:
            result: Dict[str, Any] = {}

            if source_type == ToolSourceType.OPENAPI_URL:
                openapi_url = step_data.get("openapi_url")
                if not openapi_url:
                    raise ClientException("OpenAPI URL is required")

                result = await mcp_foundry_service.create_tools_from_openapi_url(
                    url=openapi_url,
                    enhance_with_ai=step_data.get("enhance_with_ai", True),
                )

            elif source_type == ToolSourceType.API_DOCS_URL:
                api_docs_url = step_data.get("api_docs_url")
                if not api_docs_url:
                    raise ClientException("API docs URL is required")

                result = await mcp_foundry_service.create_tools_from_api_docs_url(
                    url=api_docs_url,
                    enhance_with_ai=step_data.get("enhance_with_ai", True),
                )

            elif source_type == ToolSourceType.BUD_CATALOGUE:
                # Fetch tools from selected catalogue servers
                catalogue_server_ids = step_data.get("catalogue_server_ids", [])
                all_tools = []

                for server_id in catalogue_server_ids:
                    try:
                        tools, _ = await mcp_foundry_service.list_tools(
                            server_id=server_id,
                            offset=0,
                            limit=100,  # Fetch up to 100 tools per server
                        )
                        all_tools.extend(tools)
                    except MCPFoundryException as e:
                        logger.warning(f"Failed to fetch tools for server {server_id}: {e}")
                        continue

                result = {
                    "catalogue_server_ids": catalogue_server_ids,
                    "tools": all_tools,
                    "gateway_id": catalogue_server_ids[0] if catalogue_server_ids else None,
                }

            elif source_type in (ToolSourceType.OPENAPI_FILE, ToolSourceType.API_DOCS_FILE):
                # File uploads are handled by the upload endpoint
                raise ClientException("File-based creation should use the upload endpoint")

            else:
                raise ClientException(f"Invalid source type: {source_type}")

            # Extract gateway_id and tool IDs from result
            gateway_id = result.get("gateway_id", result.get("id"))
            tools = result.get("tools", [])
            created_tool_ids = [t.get("id") for t in tools if t.get("id")]

            # Update the workflow step with full mcpgateway response
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": workflow.id}
            )

            # Find the step that triggered creation and update it with results
            for db_step in db_workflow_steps:
                if db_step.data and db_step.data.get("source_type") == source_type_str:
                    existing_data = db_step.data or {}
                    updated_data = {
                        **existing_data,
                        "gateway_id": gateway_id,
                        "created_tool_ids": created_tool_ids,
                        "mcpgateway_response": result,  # Store full response for steps/progress info
                    }
                    await WorkflowStepDataManager(self.session).update_by_fields(
                        db_step,
                        {"data": updated_data},
                    )
                    break

            # Update workflow status to completed
            await WorkflowDataManager(self.session).update_by_fields(
                workflow,
                {"status": WorkflowStatusEnum.COMPLETED},
            )

            logger.info(
                "Tool creation completed",
                workflow_id=str(workflow.id),
                gateway_id=gateway_id,
                tool_count=len(created_tool_ids),
            )

        except (ClientException, MCPFoundryException) as e:
            logger.error(f"Tool creation failed: {e}")

            # Update workflow status to failed
            await WorkflowDataManager(self.session).update_by_fields(
                workflow,
                {"status": WorkflowStatusEnum.FAILED},
            )

            error_message = e.message if hasattr(e, "message") else str(e)
            error_status = e.status_code if hasattr(e, "status_code") else status.HTTP_500_INTERNAL_SERVER_ERROR

            # Provide user-friendly error message for common errors
            if "Missing 'openapi' version field" in error_message:
                user_message = "The provided URL contains a Swagger 2.0 specification. Please provide an OpenAPI 3.0+ specification URL."
            elif "Failed to parse OpenAPI specification" in error_message:
                user_message = "Failed to parse the OpenAPI specification. Please ensure the URL points to a valid OpenAPI 3.0+ JSON or YAML file."
            else:
                user_message = f"Tool creation failed: {error_message}"

            raise ClientException(
                message=user_message,
                status_code=error_status,
            )

        except Exception as e:
            logger.exception(f"Unexpected error during tool creation: {e}")

            await WorkflowDataManager(self.session).update_by_fields(
                workflow,
                {"status": WorkflowStatusEnum.FAILED},
            )

            raise ClientException(
                message="Tool creation failed unexpectedly",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    async def upload_file_for_tool_creation(
        self,
        current_user_id: UUID,
        workflow_id: UUID,
        file_content: bytes,
        file_name: str,
        content_type: str,
        source_type: ToolSourceType,
        enhance_with_ai: bool = True,
    ) -> WorkflowModel:
        """Handle file upload for tool creation.

        Args:
            current_user_id: The ID of the current user
            workflow_id: The workflow ID
            file_content: Binary file content
            file_name: Original filename
            content_type: MIME type
            source_type: OpenAPI file or API docs file
            enhance_with_ai: Use AI enhancement

        Returns:
            Updated WorkflowModel
        """
        logger.info(
            "Processing file upload for tool creation",
            workflow_id=str(workflow_id),
            file_name=file_name,
            source_type=source_type.value,
        )

        # Get the workflow
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})

        if not db_workflow:
            raise ClientException(
                message="Workflow not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Update workflow status
        await WorkflowDataManager(self.session).update_by_fields(
            db_workflow,
            {"status": WorkflowStatusEnum.IN_PROGRESS},
        )

        try:
            # Call appropriate MCP Foundry method
            if source_type == ToolSourceType.OPENAPI_FILE:
                result = await mcp_foundry_service.create_tools_from_openapi_file(
                    file_content=file_content,
                    file_name=file_name,
                    content_type=content_type,
                    enhance_with_ai=enhance_with_ai,
                )
            elif source_type == ToolSourceType.API_DOCS_FILE:
                result = await mcp_foundry_service.create_tools_from_api_docs_file(
                    file_content=file_content,
                    file_name=file_name,
                    content_type=content_type,
                    enhance_with_ai=enhance_with_ai,
                )
            else:
                raise ClientException(f"Invalid source type for file upload: {source_type}")

            # Extract results
            gateway_id = result.get("gateway_id", result.get("id"))
            tools = result.get("tools", [])
            created_tool_ids = [t.get("id") for t in tools if t.get("id")]

            # Update or create workflow step with file info and results
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": workflow_id}
            )

            step_2_found = False
            for db_step in db_workflow_steps:
                if db_step.step_number == 2:
                    step_2_found = True
                    existing_data = db_step.data or {}
                    updated_data = {
                        **existing_data,
                        "source_type": source_type.value,
                        "uploaded_file_name": file_name,
                        "uploaded_file_content_type": content_type,
                        "enhance_with_ai": enhance_with_ai,
                        "gateway_id": gateway_id,
                        "created_tool_ids": created_tool_ids,
                        "mcpgateway_response": result,  # Store full response for steps/progress info
                    }
                    await WorkflowStepDataManager(self.session).update_by_fields(
                        db_step,
                        {"data": updated_data},
                    )
                    break

            if not step_2_found:
                await WorkflowStepDataManager(self.session).insert_one(
                    WorkflowStepModel(
                        workflow_id=workflow_id,
                        step_number=2,
                        data={
                            "source_type": source_type.value,
                            "uploaded_file_name": file_name,
                            "uploaded_file_content_type": content_type,
                            "enhance_with_ai": enhance_with_ai,
                            "gateway_id": gateway_id,
                            "created_tool_ids": created_tool_ids,
                            "mcpgateway_response": result,  # Store full response for steps/progress info
                        },
                    )
                )

            # Update workflow status to completed
            await WorkflowDataManager(self.session).update_by_fields(
                db_workflow,
                {"status": WorkflowStatusEnum.COMPLETED, "current_step": 3},
            )

            return db_workflow

        except (ClientException, MCPFoundryException) as e:
            logger.error(f"File upload tool creation failed: {e}")

            await WorkflowDataManager(self.session).update_by_fields(
                db_workflow,
                {"status": WorkflowStatusEnum.FAILED},
            )

            error_message = e.message if hasattr(e, "message") else str(e)
            error_status = e.status_code if hasattr(e, "status_code") else status.HTTP_500_INTERNAL_SERVER_ERROR

            # Provide user-friendly error message for common errors
            if "Missing 'openapi' version field" in error_message:
                user_message = "The uploaded file contains a Swagger 2.0 specification. Please upload an OpenAPI 3.0+ specification file."
            elif "Failed to parse OpenAPI specification" in error_message:
                user_message = "Failed to parse the OpenAPI specification. Please ensure the file is a valid OpenAPI 3.0+ JSON or YAML file."
            else:
                user_message = f"Tool creation failed: {error_message}"

            raise ClientException(
                message=user_message,
                status_code=error_status,
            )

    async def get_workflow(self, workflow_id: UUID, user_id: UUID) -> Dict[str, Any]:
        """Get workflow status and combined step data.

        Args:
            workflow_id: The workflow ID
            user_id: The user ID (for access validation)

        Returns:
            Dict with workflow info and combined step data
        """
        db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(WorkflowModel, {"id": workflow_id})

        if not db_workflow:
            raise ClientException(
                message="Workflow not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Get all steps and combine data
        db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
            {"workflow_id": workflow_id}
        )

        combined_data: Dict[str, Any] = {}
        for db_step in sorted(db_workflow_steps, key=lambda s: s.step_number):
            if db_step.data:
                combined_data.update(db_step.data)

        return {
            "workflow_id": db_workflow.id,
            "current_step": db_workflow.current_step,
            "total_steps": db_workflow.total_steps,
            "status": db_workflow.status,
            "step_data": combined_data,
        }

    async def get_created_tools(self, workflow_id: UUID, user_id: UUID) -> Tuple[List[ToolRead], Optional[str]]:
        """Get tools created by a workflow.

        Args:
            workflow_id: The workflow ID
            user_id: The user ID (for access validation)

        Returns:
            Tuple of (list of tools, gateway_id)
        """
        workflow_data = await self.get_workflow(workflow_id, user_id)
        step_data = workflow_data.get("step_data", {})

        gateway_id = step_data.get("gateway_id")
        created_tool_ids = step_data.get("created_tool_ids", [])

        if not created_tool_ids and not gateway_id:
            return [], None

        # If we have a gateway_id, fetch tools from it
        if gateway_id:
            try:
                gateway_data = await mcp_foundry_service.get_gateway_by_id(gateway_id)
                tools_data = gateway_data.get("tools", [])

                tool_service = ToolService(self.session)
                tools = [tool_service._transform_tool_response(t) for t in tools_data]

                return tools, gateway_id
            except MCPFoundryException as e:
                logger.warning(f"Failed to fetch gateway tools: {e}")

        # Fallback: fetch individual tools by ID
        tools = []
        tool_service = ToolService(self.session)
        for tool_id in created_tool_ids:
            try:
                tool = await tool_service.get_tool(tool_id)
                tools.append(tool)
            except ClientException:
                logger.warning(f"Tool {tool_id} not found")
                continue

        return tools, gateway_id

    async def create_virtual_server(
        self,
        workflow_id: UUID,
        user_id: UUID,
        name: str,
        tool_ids: List[str],
    ) -> Dict[str, Any]:
        """Create a virtual server with selected tools.

        Args:
            workflow_id: The workflow ID
            user_id: The user ID
            name: Virtual server name
            tool_ids: List of tool IDs to include

        Returns:
            Dict with virtual server info
        """
        logger.info(
            "Creating virtual server",
            workflow_id=str(workflow_id),
            name=name,
            tool_count=len(tool_ids),
        )

        if not tool_ids:
            raise ClientException(
                message="At least one tool must be selected",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = await mcp_foundry_service.create_virtual_server(
                name=name,
                associated_tools=tool_ids,
                visibility="public",
            )

            virtual_server_id = result.get("id")

            # Update workflow step with virtual server info
            db_workflow_steps = await WorkflowStepDataManager(self.session).get_all_workflow_steps(
                {"workflow_id": workflow_id}
            )

            # Find step 5 or create it
            step_5_found = False
            for db_step in db_workflow_steps:
                if db_step.step_number == 5:
                    step_5_found = True
                    existing_data = db_step.data or {}
                    updated_data = {
                        **existing_data,
                        "virtual_server_name": name,
                        "virtual_server_id": virtual_server_id,
                        "selected_tool_ids": tool_ids,
                    }
                    await WorkflowStepDataManager(self.session).update_by_fields(
                        db_step,
                        {"data": updated_data},
                    )
                    break

            if not step_5_found:
                await WorkflowStepDataManager(self.session).insert_one(
                    WorkflowStepModel(
                        workflow_id=workflow_id,
                        step_number=5,
                        data={
                            "virtual_server_name": name,
                            "virtual_server_id": virtual_server_id,
                            "selected_tool_ids": tool_ids,
                        },
                    )
                )

            # Update workflow to completed
            db_workflow = await WorkflowDataManager(self.session).retrieve_by_fields(
                WorkflowModel, {"id": workflow_id}
            )
            await WorkflowDataManager(self.session).update_by_fields(
                db_workflow,
                {"status": WorkflowStatusEnum.COMPLETED, "current_step": 5},
            )

            logger.info(
                "Virtual server created",
                workflow_id=str(workflow_id),
                virtual_server_id=virtual_server_id,
            )

            return {
                "virtual_server_id": virtual_server_id,
                "name": name,
                "tool_count": len(tool_ids),
            }

        except MCPFoundryException as e:
            logger.error(f"Failed to create virtual server: {e}")
            raise ClientException(
                message=f"Failed to create virtual server: {e.message}",
                status_code=e.status_code,
            )

    async def list_catalogue_servers(
        self,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[CatalogueServerRead], int]:
        """List available servers from the Bud catalogue.

        Args:
            offset: Number of items to skip
            limit: Maximum items to return

        Returns:
            Tuple of (list of servers, total count)
        """
        try:
            servers, total = await mcp_foundry_service.list_catalogue_servers(
                show_registered_only=False,
                show_available_only=True,
                offset=offset,
                limit=limit,
            )

            catalogue_servers = [
                CatalogueServerRead(
                    id=s.get("id", ""),
                    name=s.get("name", ""),
                    description=s.get("description"),
                    icon=s.get("icon"),
                    url=s.get("url"),
                    transport=s.get("transport"),
                    is_registered=s.get("isRegistered", False),
                    tools_count=s.get("toolsCount"),
                )
                for s in servers
            ]

            return catalogue_servers, total

        except MCPFoundryException as e:
            logger.error(f"Failed to list catalogue servers: {e}")
            raise ClientException(
                message=f"Failed to list catalogue servers: {e.message}",
                status_code=e.status_code,
            )

    async def list_virtual_servers(
        self,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[VirtualServerRead], int]:
        """List virtual servers from MCP Foundry.

        Args:
            offset: Number of items to skip
            limit: Maximum items to return

        Returns:
            Tuple of (list of virtual servers, total count)
        """
        try:
            servers, total = await mcp_foundry_service.list_virtual_servers(
                offset=offset,
                limit=limit,
            )

            virtual_servers = [
                VirtualServerRead(
                    id=s.get("id", ""),
                    name=s.get("name", ""),
                    description=s.get("description"),
                    visibility=s.get("visibility"),
                    associated_tools=s.get("associatedTools", s.get("associated_tools", [])),
                    tools_count=len(s.get("associatedTools", s.get("associated_tools", []))),
                    created_at=s.get("createdAt"),
                    updated_at=s.get("updatedAt"),
                )
                for s in servers
            ]

            return virtual_servers, total

        except MCPFoundryException as e:
            logger.error(f"Failed to list virtual servers: {e}")
            raise ClientException(
                message=f"Failed to list virtual servers: {e.message}",
                status_code=e.status_code,
            )

    async def get_virtual_server_by_id(
        self,
        server_id: str,
    ) -> Dict[str, Any]:
        """Get a virtual server by ID with its associated tools.

        Args:
            server_id: The virtual server ID

        Returns:
            Dict containing virtual server data with tools array
        """
        try:
            server_data = await mcp_foundry_service.get_virtual_server_by_id(
                server_id=server_id,
            )

            # Fetch tools for this virtual server directly from MCP Foundry
            try:
                tools = await mcp_foundry_service.get_virtual_server_tools(
                    server_id=server_id,
                    include_inactive=False,
                )
            except MCPFoundryException as e:
                logger.warning(f"Failed to fetch tools for server {server_id}: {e}")
                tools = []

            # Add tools array to the response
            server_data["tools"] = tools

            return server_data

        except MCPFoundryException as e:
            logger.error(f"Failed to get virtual server {server_id}: {e}")
            raise ClientException(
                message=f"Failed to get virtual server: {e.message}",
                status_code=e.status_code,
            )

    async def update_virtual_server_by_id(
        self,
        server_id: str,
        update_data: VirtualServerUpdateRequest,
    ) -> Dict[str, Any]:
        """Update a virtual server.

        Args:
            server_id: The virtual server ID
            update_data: Fields to update

        Returns:
            Updated virtual server data
        """
        logger.info(
            "Updating virtual server",
            server_id=server_id,
            update_fields=list(update_data.model_dump(exclude_none=True).keys()),
        )

        try:
            # Get current server data first to merge with updates
            current_data = await mcp_foundry_service.get_virtual_server_by_id(server_id)

            # Build update payload
            update_payload: Dict[str, Any] = {}

            if update_data.name is not None:
                update_payload["name"] = update_data.name
            if update_data.description is not None:
                update_payload["description"] = update_data.description
            if update_data.visibility is not None:
                update_payload["visibility"] = update_data.visibility
            if update_data.associated_tools is not None:
                update_payload["associated_tools"] = update_data.associated_tools

            if not update_payload:
                # No updates provided, return current data
                return current_data

            # Use existing associated_tools if not provided
            if "associated_tools" not in update_payload:
                update_payload["associated_tools"] = current_data.get(
                    "associatedTools", current_data.get("associated_tools", [])
                )

            result = await mcp_foundry_service.update_virtual_server(
                server_id=server_id,
                associated_tools=update_payload.get("associated_tools", []),
            )

            logger.info(f"Successfully updated virtual server {server_id}")
            return result

        except MCPFoundryException as e:
            if e.status_code == 404:
                raise ClientException(
                    message=f"Virtual server {server_id} not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            logger.error(f"Failed to update virtual server {server_id}: {e}")
            raise ClientException(
                message=f"Failed to update virtual server: {e.message}",
                status_code=e.status_code,
            )

    async def delete_virtual_server_by_id(
        self,
        server_id: str,
    ) -> None:
        """Delete a virtual server.

        Args:
            server_id: The virtual server ID to delete
        """
        logger.info(f"Deleting virtual server {server_id}")

        try:
            await mcp_foundry_service.delete_virtual_server(server_id=server_id)
            logger.info(f"Successfully deleted virtual server {server_id}")

        except MCPFoundryException as e:
            if e.status_code == 404:
                raise ClientException(
                    message=f"Virtual server {server_id} not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            logger.error(f"Failed to delete virtual server {server_id}: {e}")
            raise ClientException(
                message=f"Failed to delete virtual server: {e.message}",
                status_code=e.status_code,
            )

    async def create_standalone_virtual_server(
        self,
        name: str,
        tool_ids: List[str],
        description: Optional[str] = None,
        visibility: str = "public",
    ) -> Dict[str, Any]:
        """Create a virtual server without a workflow context.

        Args:
            name: Virtual server name
            tool_ids: List of tool IDs to include
            description: Virtual server description
            visibility: Visibility level (public, private)

        Returns:
            Dict with virtual server info
        """
        logger.info(
            "Creating standalone virtual server",
            name=name,
            tool_count=len(tool_ids),
        )

        if not tool_ids:
            raise ClientException(
                message="At least one tool must be selected",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = await mcp_foundry_service.create_virtual_server(
                name=name,
                associated_tools=tool_ids,
                visibility=visibility,
            )

            virtual_server_id = result.get("id")

            logger.info(
                "Standalone virtual server created",
                virtual_server_id=virtual_server_id,
                name=name,
            )

            return {
                "virtual_server_id": virtual_server_id,
                "name": name,
                "tool_count": len(tool_ids),
            }

        except MCPFoundryException as e:
            logger.error(f"Failed to create virtual server: {e}")
            raise ClientException(
                message=f"Failed to create virtual server: {e.message}",
                status_code=e.status_code,
            )
