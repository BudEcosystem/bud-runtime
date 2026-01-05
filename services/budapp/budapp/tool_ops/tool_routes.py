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

"""API routes for the tool operations module.

This module provides routes for:
- Tool CRUD operations (list, get, update, delete)
- Tool creation workflows (multi-step workflow for creating tools from various sources)
- Tool catalogue (browsing Bud catalogue servers)
- Virtual server CRUD operations (list, get, create, update, delete)
"""

from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.dependencies import get_current_active_user, get_session
from budapp.commons.exceptions import ClientException
from budapp.commons.schemas import ErrorResponse
from budapp.user_ops.schemas import User

from .schemas import (
    CatalogueListResponse,
    CreatedToolsListResponse,
    CreateToolWorkflowRequest,
    SingleToolResponse,
    ToolCreationWorkflowResponse,
    ToolDeleteResponse,
    ToolListResponse,
    ToolRead,
    ToolSourceType,
    ToolUpdate,
    VirtualServerCreateRequest,
    VirtualServerDeleteResponse,
    VirtualServerDetailResponse,
    VirtualServerListResponse,
    VirtualServerResponse,
    VirtualServerUpdateRequest,
)
from .services import ToolCreationWorkflowService, ToolService


logger = logging.get_logger(__name__)

# Main tool router with all sub-routes
tool_router = APIRouter(prefix="/tools", tags=["tools"])


# =============================================================================
# Tool CRUD Routes
# =============================================================================


@tool_router.get(
    "",
    response_class=JSONResponse,
    responses={
        status.HTTP_200_OK: {
            "model": ToolListResponse,
            "description": "Successfully listed tools",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request data",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="List all tools from MCP Gateway with optional filtering",
)
async def list_tools(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    cursor: Optional[str] = Query(None, description="Pagination cursor for next page"),
    include_inactive: bool = Query(False, description="Include inactive tools"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    visibility: Optional[str] = Query(None, description="Filter by visibility (public, private)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
) -> JSONResponse:
    """List all tools from MCP Gateway with optional filtering."""
    offset = (page - 1) * limit

    try:
        tools, total_count, next_cursor = await ToolService(session).list_tools(
            cursor=cursor,
            include_inactive=include_inactive,
            tags=tags,
            team_id=team_id,
            visibility=visibility,
            offset=offset,
            limit=limit,
        )

        return ToolListResponse(
            tools=tools,
            total_record=total_count,
            page=page,
            limit=limit,
            next_cursor=next_cursor,
            object="tools.list",
            code=status.HTTP_200_OK,
            message="Tools listed successfully",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to list tools: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list tools: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list tools"
        ).to_http_response()


@tool_router.get(
    "/catalogue",
    response_class=JSONResponse,
    responses={
        status.HTTP_200_OK: {
            "model": CatalogueListResponse,
            "description": "Successfully listed catalogue servers",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="List available servers from Bud catalogue",
)
async def list_catalogue_servers(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum items to return"),
) -> JSONResponse:
    """List available servers from the Bud catalogue (MCP registry)."""
    try:
        servers, total = await ToolCreationWorkflowService(session).list_catalogue_servers(
            offset=offset,
            limit=limit,
        )

        return CatalogueListResponse(
            servers=servers,
            total=total,
            code=status.HTTP_200_OK,
            message="Catalogue servers retrieved successfully",
            object="tool_catalogue.list",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to list catalogue servers: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list catalogue servers: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve catalogue servers",
        ).to_http_response()


@tool_router.get(
    "/{tool_id}",
    response_class=JSONResponse,
    responses={
        status.HTTP_200_OK: {
            "model": SingleToolResponse,
            "description": "Successfully retrieved tool",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Tool not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Retrieve a single tool by ID from MCP Gateway",
)
async def get_tool(
    tool_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JSONResponse:
    """Retrieve a single tool by ID from MCP Gateway."""
    try:
        tool = await ToolService(session).get_tool(tool_id)

        return SingleToolResponse(
            tool=tool,
            message="Tool retrieved successfully",
            code=status.HTTP_200_OK,
            object="tool.get",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to get tool {tool_id}: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get tool {tool_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to retrieve tool"
        ).to_http_response()


@tool_router.put(
    "/{tool_id}",
    response_class=JSONResponse,
    responses={
        status.HTTP_200_OK: {
            "model": SingleToolResponse,
            "description": "Successfully updated tool",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Tool not found",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request data",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Update a tool by ID in MCP Gateway",
)
async def update_tool(
    tool_id: str,
    update_data: ToolUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JSONResponse:
    """Update a tool by ID in MCP Gateway."""
    try:
        tool = await ToolService(session).update_tool(tool_id, update_data)

        return SingleToolResponse(
            tool=tool,
            message="Tool updated successfully",
            code=status.HTTP_200_OK,
            object="tool.update",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to update tool {tool_id}: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to update tool {tool_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to update tool"
        ).to_http_response()


@tool_router.delete(
    "/{tool_id}",
    response_class=JSONResponse,
    responses={
        status.HTTP_200_OK: {
            "model": ToolDeleteResponse,
            "description": "Successfully deleted tool",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Tool not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Delete a tool by ID from MCP Gateway",
)
async def delete_tool(
    tool_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JSONResponse:
    """Delete a tool by ID from MCP Gateway."""
    try:
        await ToolService(session).delete_tool(tool_id)

        return ToolDeleteResponse(
            id=tool_id,
            message="Tool deleted successfully",
            code=status.HTTP_200_OK,
            object="tool.delete",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to delete tool {tool_id}: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete tool {tool_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to delete tool"
        ).to_http_response()


# =============================================================================
# Tool Creation Workflow Routes
# =============================================================================


tool_workflow_router = APIRouter(prefix="/tools/workflow", tags=["tool-workflow"])


@tool_workflow_router.post(
    "",
    response_class=JSONResponse,
    responses={
        status.HTTP_200_OK: {
            "model": ToolCreationWorkflowResponse,
            "description": "Successfully created/updated workflow step",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request data",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Create or update a tool creation workflow step",
)
async def create_or_update_workflow(
    request: CreateToolWorkflowRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JSONResponse:
    """Create or update a tool creation workflow step."""
    try:
        workflow = await ToolCreationWorkflowService(session).add_tool_workflow(
            current_user_id=current_user.id,
            request=request,
        )

        return ToolCreationWorkflowResponse(
            workflow_id=workflow.id,
            current_step=workflow.current_step,
            total_steps=workflow.total_steps,
            status=workflow.status,
            step_data=None,
            code=status.HTTP_200_OK,
            message="Workflow step saved successfully",
            object="tool_workflow.create",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to create/update workflow: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to create/update workflow: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to process workflow step",
        ).to_http_response()


@tool_workflow_router.post(
    "/{workflow_id}/upload",
    response_class=JSONResponse,
    responses={
        status.HTTP_200_OK: {
            "model": ToolCreationWorkflowResponse,
            "description": "Successfully uploaded file and created tools",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request data",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Workflow not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Upload a file for tool creation (OpenAPI spec or API docs)",
)
async def upload_file_for_workflow(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    file: UploadFile = File(..., description="OpenAPI spec or API docs file"),
    source_type: ToolSourceType = Form(..., description="Source type (openapi_file or api_docs_file)"),
    enhance_with_ai: bool = Form(True, description="Use AI to enhance tool descriptions"),
) -> JSONResponse:
    """Upload a file for tool creation."""
    try:
        if source_type not in (ToolSourceType.OPENAPI_FILE, ToolSourceType.API_DOCS_FILE):
            raise ClientException(
                message="Invalid source type for file upload. Use 'openapi_file' or 'api_docs_file'",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        file_content = await file.read()
        file_name = file.filename or "uploaded_file"
        content_type = file.content_type or "application/octet-stream"

        workflow = await ToolCreationWorkflowService(session).upload_file_for_tool_creation(
            current_user_id=current_user.id,
            workflow_id=workflow_id,
            file_content=file_content,
            file_name=file_name,
            content_type=content_type,
            source_type=source_type,
            enhance_with_ai=enhance_with_ai,
        )

        return ToolCreationWorkflowResponse(
            workflow_id=workflow.id,
            current_step=workflow.current_step,
            total_steps=workflow.total_steps,
            status=workflow.status,
            step_data=None,
            code=status.HTTP_200_OK,
            message="File processed and tools created successfully",
            object="tool_workflow.upload",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to upload file: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to upload file: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to process uploaded file",
        ).to_http_response()


@tool_workflow_router.get(
    "/{workflow_id}",
    response_class=JSONResponse,
    responses={
        status.HTTP_200_OK: {
            "model": ToolCreationWorkflowResponse,
            "description": "Successfully retrieved workflow",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Workflow not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Get workflow status and data",
)
async def get_workflow(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JSONResponse:
    """Get workflow status and combined step data."""
    try:
        workflow_data = await ToolCreationWorkflowService(session).get_workflow(
            workflow_id=workflow_id,
            user_id=current_user.id,
        )

        return ToolCreationWorkflowResponse(
            workflow_id=workflow_data["workflow_id"],
            current_step=workflow_data["current_step"],
            total_steps=workflow_data["total_steps"],
            status=workflow_data["status"],
            step_data=workflow_data["step_data"],
            code=status.HTTP_200_OK,
            message="Workflow retrieved successfully",
            object="tool_workflow.get",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to get workflow: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get workflow: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve workflow",
        ).to_http_response()


@tool_workflow_router.get(
    "/{workflow_id}/tools",
    response_class=JSONResponse,
    responses={
        status.HTTP_200_OK: {
            "model": CreatedToolsListResponse,
            "description": "Successfully retrieved created tools",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Workflow not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Get tools created by a workflow",
)
async def get_workflow_tools(
    workflow_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JSONResponse:
    """Get the list of tools created by a workflow."""
    try:
        tools, gateway_id = await ToolCreationWorkflowService(session).get_created_tools(
            workflow_id=workflow_id,
            user_id=current_user.id,
        )

        return CreatedToolsListResponse(
            tools=tools,
            gateway_id=gateway_id,
            code=status.HTTP_200_OK,
            message="Tools retrieved successfully",
            object="tool_workflow.tools",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to get workflow tools: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get workflow tools: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve tools",
        ).to_http_response()


@tool_workflow_router.post(
    "/{workflow_id}/virtual-server",
    response_class=JSONResponse,
    responses={
        status.HTTP_200_OK: {
            "model": VirtualServerResponse,
            "description": "Successfully created virtual server",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request data",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Workflow not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Create a virtual server with selected tools from a workflow",
)
async def create_virtual_server_from_workflow(
    workflow_id: UUID,
    request: VirtualServerCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JSONResponse:
    """Create a virtual server with selected tools from the workflow."""
    try:
        result = await ToolCreationWorkflowService(session).create_virtual_server(
            workflow_id=workflow_id,
            user_id=current_user.id,
            name=request.name,
            tool_ids=request.selected_tool_ids,
        )

        return VirtualServerResponse(
            virtual_server_id=result["virtual_server_id"],
            name=result["name"],
            tool_count=result["tool_count"],
            code=status.HTTP_200_OK,
            message="Virtual server created successfully",
            object="tool_workflow.virtual_server",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to create virtual server: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to create virtual server: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create virtual server",
        ).to_http_response()


# =============================================================================
# Virtual Server Routes
# =============================================================================


virtual_server_router = APIRouter(prefix="/tools/virtual-servers", tags=["virtual-servers"])


@virtual_server_router.get(
    "",
    response_class=JSONResponse,
    responses={
        status.HTTP_200_OK: {
            "model": VirtualServerListResponse,
            "description": "Successfully listed virtual servers",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="List virtual servers",
)
async def list_virtual_servers(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum items to return"),
) -> JSONResponse:
    """List virtual servers from MCP Foundry."""
    try:
        servers, total = await ToolCreationWorkflowService(session).list_virtual_servers(
            offset=offset,
            limit=limit,
        )

        page = (offset // limit) + 1 if limit > 0 else 1

        return VirtualServerListResponse(
            servers=servers,
            total=total,
            page=page,
            limit=limit,
            total_record=total,
            code=status.HTTP_200_OK,
            message="Virtual servers retrieved successfully",
            object="virtual_servers.list",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to list virtual servers: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list virtual servers: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve virtual servers",
        ).to_http_response()


@virtual_server_router.post(
    "",
    response_class=JSONResponse,
    responses={
        status.HTTP_200_OK: {
            "model": VirtualServerResponse,
            "description": "Successfully created virtual server",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request data",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Create a new virtual server",
)
async def create_virtual_server(
    request: VirtualServerCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JSONResponse:
    """Create a new virtual server with selected tools."""
    try:
        result = await ToolCreationWorkflowService(session).create_standalone_virtual_server(
            name=request.name,
            tool_ids=request.selected_tool_ids,
        )

        return VirtualServerResponse(
            virtual_server_id=result["virtual_server_id"],
            name=result["name"],
            tool_count=result["tool_count"],
            code=status.HTTP_200_OK,
            message="Virtual server created successfully",
            object="virtual_servers.create",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to create virtual server: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to create virtual server: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create virtual server",
        ).to_http_response()


@virtual_server_router.get(
    "/{server_id}",
    response_class=JSONResponse,
    responses={
        status.HTTP_200_OK: {
            "model": VirtualServerDetailResponse,
            "description": "Successfully retrieved virtual server",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Virtual server not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Get a virtual server by ID with its tools",
)
async def get_virtual_server(
    server_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JSONResponse:
    """Get a virtual server by ID with its associated tools."""
    try:
        server_data = await ToolCreationWorkflowService(session).get_virtual_server_by_id(
            server_id=server_id,
        )

        tools_list = server_data.get("tools", [])
        tools = [ToolRead.model_validate(tool) for tool in tools_list]

        return VirtualServerDetailResponse(
            id=server_data.get("id", server_id),
            name=server_data.get("name", ""),
            description=server_data.get("description"),
            visibility=server_data.get("visibility"),
            tools=tools,
            tools_count=len(tools),
            created_at=server_data.get("createdAt"),
            updated_at=server_data.get("updatedAt"),
            code=status.HTTP_200_OK,
            message="Virtual server retrieved successfully",
            object="virtual_servers.get",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to get virtual server: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get virtual server: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve virtual server",
        ).to_http_response()


@virtual_server_router.put(
    "/{server_id}",
    response_class=JSONResponse,
    responses={
        status.HTTP_200_OK: {
            "model": VirtualServerDetailResponse,
            "description": "Successfully updated virtual server",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Virtual server not found",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid request data",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Update a virtual server by ID",
)
async def update_virtual_server(
    server_id: str,
    update_data: VirtualServerUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JSONResponse:
    """Update a virtual server by ID."""
    try:
        await ToolCreationWorkflowService(session).update_virtual_server_by_id(
            server_id=server_id,
            update_data=update_data,
        )

        # Get full server data with tools after update
        server_data = await ToolCreationWorkflowService(session).get_virtual_server_by_id(
            server_id=server_id,
        )

        tools_list = server_data.get("tools", [])
        tools = [ToolRead.model_validate(tool) for tool in tools_list]

        return VirtualServerDetailResponse(
            id=server_data.get("id", server_id),
            name=server_data.get("name", ""),
            description=server_data.get("description"),
            visibility=server_data.get("visibility"),
            tools=tools,
            tools_count=len(tools),
            created_at=server_data.get("createdAt"),
            updated_at=server_data.get("updatedAt"),
            code=status.HTTP_200_OK,
            message="Virtual server updated successfully",
            object="virtual_servers.update",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to update virtual server {server_id}: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to update virtual server {server_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update virtual server",
        ).to_http_response()


@virtual_server_router.delete(
    "/{server_id}",
    response_class=JSONResponse,
    responses={
        status.HTTP_200_OK: {
            "model": VirtualServerDeleteResponse,
            "description": "Successfully deleted virtual server",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Virtual server not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Server error",
        },
    },
    description="Delete a virtual server by ID",
)
async def delete_virtual_server(
    server_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
) -> JSONResponse:
    """Delete a virtual server by ID."""
    try:
        await ToolCreationWorkflowService(session).delete_virtual_server_by_id(
            server_id=server_id,
        )

        return VirtualServerDeleteResponse(
            id=server_id,
            message="Virtual server deleted successfully",
            code=status.HTTP_200_OK,
            object="virtual_servers.delete",
        ).to_http_response()

    except ClientException as e:
        logger.error(f"Failed to delete virtual server {server_id}: {e}")
        return ErrorResponse(code=e.status_code, message=e.message).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete virtual server {server_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete virtual server",
        ).to_http_response()
