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

"""Pydantic schemas for tool operations module."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..commons.schemas import PaginatedSuccessResponse, SuccessResponse


class ToolSourceType(str, Enum):
    """Enum for tool creation source types."""

    OPENAPI_URL = "openapi_url"
    OPENAPI_FILE = "openapi_file"
    API_DOCS_URL = "api_docs_url"
    API_DOCS_FILE = "api_docs_file"
    BUD_CATALOGUE = "bud_catalogue"


class ToolRead(BaseModel):
    """Schema for tool data returned from MCP Foundry."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    name: str = Field(description="Original name of the tool")
    display_name: Optional[str] = Field(None, alias="displayName", description="Display name for UI")
    custom_name: Optional[str] = Field(None, alias="customName", description="Custom name set by user")
    url: Optional[str] = Field(None, description="Tool endpoint URL")
    description: Optional[str] = Field(None, description="Tool description")
    integration_type: Optional[str] = Field(
        None, alias="integrationType", description="Integration type (REST, MCP, A2A)"
    )
    request_type: Optional[str] = Field(None, alias="requestType", description="HTTP method (GET, POST, etc.)")
    headers: Optional[Dict[str, Any]] = Field(None, description="Request headers")
    input_schema: Optional[Dict[str, Any]] = Field(None, alias="inputSchema", description="Input parameter schema")
    output_schema: Optional[Dict[str, Any]] = Field(None, alias="outputSchema", description="Output schema")
    annotations: Optional[Dict[str, Any]] = Field(None, description="Tool annotations")
    is_active: bool = Field(True, alias="isActive", description="Whether tool is active")
    enabled: bool = Field(True, description="Whether tool is enabled")
    reachable: bool = Field(True, description="Whether tool endpoint is reachable")
    visibility: Optional[str] = Field(None, description="Visibility level (public, private)")
    tags: Optional[List[str]] = Field(None, description="Tool tags")
    team_id: Optional[str] = Field(None, alias="teamId", description="Team ID")
    server_id: Optional[str] = Field(None, alias="serverId", description="Gateway/Server ID")
    gateway_id: Optional[str] = Field(None, alias="gatewayId", description="Gateway ID")
    auth: Optional[Dict[str, Any]] = Field(None, description="Authentication configuration")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Tool execution metrics")
    created_at: Optional[datetime] = Field(None, alias="createdAt", description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt", description="Last update timestamp")


class ToolUpdate(BaseModel):
    """Schema for updating a tool. All fields are optional for partial updates."""

    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(None, description="Tool name")
    display_name: Optional[str] = Field(None, alias="displayName", description="Display name for UI")
    custom_name: Optional[str] = Field(None, alias="customName", description="Custom name set by user")
    url: Optional[str] = Field(None, description="Tool endpoint URL")
    description: Optional[str] = Field(None, description="Tool description")
    integration_type: Optional[str] = Field(None, alias="integrationType", description="Integration type")
    request_type: Optional[str] = Field(None, alias="requestType", description="HTTP method")
    headers: Optional[Dict[str, Any]] = Field(None, description="Request headers")
    input_schema: Optional[Dict[str, Any]] = Field(None, alias="inputSchema", description="Input schema")
    output_schema: Optional[Dict[str, Any]] = Field(None, alias="outputSchema", description="Output schema")
    is_active: Optional[bool] = Field(None, alias="isActive", description="Whether tool is active")
    visibility: Optional[str] = Field(None, description="Visibility level")
    tags: Optional[List[str]] = Field(None, description="Tool tags")


class ToolListResponse(PaginatedSuccessResponse):
    """Paginated tool list response schema."""

    model_config = ConfigDict(extra="ignore")

    tools: List[ToolRead] = Field(default_factory=list, description="List of tools")
    next_cursor: Optional[str] = Field(None, alias="nextCursor", description="Cursor for next page")


class SingleToolResponse(SuccessResponse):
    """Single tool response schema."""

    tool: ToolRead = Field(..., description="Tool data")


class ToolDeleteResponse(SuccessResponse):
    """Tool deletion response schema."""

    id: str = Field(..., description="ID of the deleted tool")


# ============================================================================
# Tool Creation Workflow Schemas
# ============================================================================


class CreateToolWorkflowRequest(BaseModel):
    """Request schema for creating/updating a tool creation workflow step."""

    model_config = ConfigDict(populate_by_name=True)

    workflow_id: Optional[UUID] = Field(None, description="Existing workflow ID, if resuming")
    workflow_total_steps: int = Field(5, description="Total steps in the workflow")
    step_number: int = Field(1, ge=1, le=5, description="Current step number (1-5)")
    source_type: Optional[ToolSourceType] = Field(None, description="Tool source type")

    # Step 2: URL inputs (mutually exclusive with file upload)
    openapi_url: Optional[str] = Field(None, description="OpenAPI specification URL")
    api_docs_url: Optional[str] = Field(None, description="API documentation URL")
    enhance_with_ai: bool = Field(True, description="Use AI to enhance tool descriptions")

    # Step 2: Catalogue selection
    catalogue_server_ids: Optional[List[str]] = Field(None, description="Selected servers from Bud Catalogue")

    # Step 4: Tool selection
    selected_tool_ids: Optional[List[str]] = Field(None, description="Selected tool IDs for virtual server")

    # Step 5: Virtual server
    virtual_server_name: Optional[str] = Field(None, description="Name for the virtual server")

    # Trigger execution
    trigger_workflow: bool = Field(False, description="Trigger tool creation execution")


class ToolCreationWorkflowStepData(BaseModel):
    """Schema for workflow step data stored in JSONB."""

    model_config = ConfigDict(populate_by_name=True)

    source_type: Optional[ToolSourceType] = None
    openapi_url: Optional[str] = None
    api_docs_url: Optional[str] = None
    enhance_with_ai: bool = True
    catalogue_server_ids: Optional[List[str]] = None
    uploaded_file_name: Optional[str] = None
    uploaded_file_content_type: Optional[str] = None

    # Results from tool creation
    gateway_id: Optional[str] = None
    created_tool_ids: Optional[List[str]] = None

    # Tool selection and virtual server
    selected_tool_ids: Optional[List[str]] = None
    virtual_server_name: Optional[str] = None
    virtual_server_id: Optional[str] = None


class ToolCreationStatus(str, Enum):
    """Status values for tool creation workflow."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolCreationWorkflowResponse(SuccessResponse):
    """Response schema for tool creation workflow operations."""

    model_config = ConfigDict(populate_by_name=True)

    workflow_id: UUID = Field(..., description="Workflow ID")
    current_step: int = Field(..., description="Current step number")
    total_steps: int = Field(..., description="Total steps in workflow")
    status: str = Field(..., description="Workflow status")
    step_data: Optional[Dict[str, Any]] = Field(None, description="Combined step data")


class CreatedToolsListResponse(SuccessResponse):
    """Response schema for listing tools created by a workflow."""

    model_config = ConfigDict(populate_by_name=True)

    tools: List[ToolRead] = Field(default_factory=list, description="List of created tools")
    gateway_id: Optional[str] = Field(None, description="Gateway ID used for tool creation")


class VirtualServerCreateRequest(BaseModel):
    """Request schema for creating a virtual server."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255, description="Virtual server name")
    selected_tool_ids: List[str] = Field(..., min_length=1, description="List of tool IDs to include")


class VirtualServerResponse(SuccessResponse):
    """Response schema for virtual server operations."""

    model_config = ConfigDict(populate_by_name=True)

    virtual_server_id: str = Field(..., description="Created virtual server ID")
    name: str = Field(..., description="Virtual server name")
    tool_count: int = Field(..., description="Number of tools in the virtual server")


class CatalogueServerRead(BaseModel):
    """Schema for catalogue server data from MCP registry."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str = Field(..., description="Server ID")
    name: str = Field(..., description="Server name")
    description: Optional[str] = Field(None, description="Server description")
    icon: Optional[str] = Field(None, description="Server icon URL")
    url: Optional[str] = Field(None, description="Server URL")
    transport: Optional[str] = Field(None, description="Transport type (SSE, stdio)")
    is_registered: bool = Field(False, alias="isRegistered", description="Whether server is registered")
    tools_count: Optional[int] = Field(None, alias="toolsCount", description="Number of tools available")


class CatalogueListResponse(SuccessResponse):
    """Response schema for listing Bud catalogue servers."""

    model_config = ConfigDict(populate_by_name=True)

    servers: List[CatalogueServerRead] = Field(default_factory=list, description="List of catalogue servers")
    total: int = Field(0, description="Total number of servers")


class VirtualServerRead(BaseModel):
    """Schema for virtual server data from MCP Foundry."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str = Field(..., description="Virtual server ID")
    name: str = Field(..., description="Virtual server name")
    description: Optional[str] = Field(None, description="Virtual server description")
    visibility: Optional[str] = Field(None, description="Visibility level (public, private)")
    associated_tools: Optional[List[str]] = Field(
        None, alias="associatedTools", description="List of associated tool IDs"
    )
    tools_count: Optional[int] = Field(None, alias="toolsCount", description="Number of associated tools")
    created_at: Optional[datetime] = Field(None, alias="createdAt", description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt", description="Last update timestamp")


class VirtualServerListResponse(PaginatedSuccessResponse):
    """Response schema for listing virtual servers."""

    model_config = ConfigDict(populate_by_name=True)

    servers: List[VirtualServerRead] = Field(default_factory=list, description="List of virtual servers")
    total: int = Field(0, description="Total number of virtual servers")


class VirtualServerDetailResponse(SuccessResponse):
    """Response schema for a single virtual server with tools."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Virtual server ID")
    name: str = Field(..., description="Virtual server name")
    description: Optional[str] = Field(None, description="Virtual server description")
    visibility: Optional[str] = Field(None, description="Visibility level (public, private)")
    tools: List[ToolRead] = Field(default_factory=list, description="List of tools in the virtual server")
    tools_count: int = Field(0, alias="toolsCount", description="Number of tools")
    created_at: Optional[datetime] = Field(None, alias="createdAt", description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt", description="Last update timestamp")


class VirtualServerUpdateRequest(BaseModel):
    """Request schema for updating a virtual server."""

    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Virtual server name")
    description: Optional[str] = Field(None, description="Virtual server description")
    visibility: Optional[str] = Field(None, description="Visibility level (public, private)")
    associated_tools: Optional[List[str]] = Field(
        None, alias="associatedTools", description="List of tool IDs (replaces existing)"
    )


class VirtualServerDeleteResponse(SuccessResponse):
    """Response schema for virtual server deletion."""

    id: str = Field(..., description="ID of the deleted virtual server")
