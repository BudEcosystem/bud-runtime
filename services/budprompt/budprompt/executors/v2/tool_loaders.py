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

"""Tool loaders for loading and managing different types of tools (MCP, custom, etc.)."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from budmicroframe.commons import logging
from pydantic_ai.mcp import MCPServerStreamableHTTP

from budprompt.commons.config import app_settings

from ...prompt.schemas import MCPToolConfig


logger = logging.get_logger(__name__)


class ToolLoader(ABC):
    """Abstract base class for tool loaders."""

    @abstractmethod
    async def load_tools(self, tool_config: Any) -> Optional[Any]:
        """Load and return toolset from configuration.

        Args:
            tool_config: Tool configuration object

        Returns:
            Toolset object or None if loading fails
        """
        pass


class MCPToolLoader(ToolLoader):
    """Loader for MCP (Model Context Protocol) tools."""

    def __init__(self):
        """Initialize MCP tool loader with config from settings."""
        self.base_url = app_settings.mcp_foundry_base_url
        self.api_key = app_settings.mcp_foundry_api_key

    async def load_tools(self, tool_config: MCPToolConfig) -> Optional[MCPServerStreamableHTTP]:
        """Load MCP tools from configuration.

        Args:
            tool_config: MCP tool configuration

        Returns:
            MCPServerStreamableHTTP instance or None if server_url is missing
        """
        # Only create toolset if server_url is present
        if not tool_config.server_url:
            logger.warning(f"Skipping MCP tool '{tool_config.server_label}': server_url is missing")
            return None

        try:
            # Construct full MCP endpoint URL
            mcp_url = f"{self.base_url}servers/{tool_config.server_url}/mcp"

            # Prepare headers with authorization if api_key is provided
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # Create MCPServerStreamableHTTP instance
            mcp_server = MCPServerStreamableHTTP(url=mcp_url, headers=headers if headers else None)

            logger.debug(
                f"Loaded MCP tool '{tool_config.server_label}' from {mcp_url} "
                f"with {len(tool_config.allowed_tools)} allowed tools"
            )

            return mcp_server

        except Exception as e:
            logger.error(f"Failed to load MCP tool '{tool_config.server_label}': {str(e)}")
            return None

    async def get_tool_list(self, mcp_server: MCPServerStreamableHTTP, server_label: str) -> Optional[Dict]:
        """Fetch the list of available tools from an MCP server.

        Args:
            mcp_server: The MCP server instance
            server_label: Label for the server (for logging)

        Returns:
            Dictionary with tools list or None on error
        """
        try:
            # Use the MCP server's list_tools method
            # This is provided by pydantic-ai's MCPServerStreamableHTTP
            tools_list = await mcp_server.list_tools()

            logger.debug(f"Retrieved {len(tools_list)} tools from MCP server '{server_label}'")

            return {"server_label": server_label, "tools": tools_list, "error": None}

        except Exception as e:
            error_msg = f"Failed to list tools from MCP server '{server_label}': {str(e)}"
            logger.error(error_msg)
            return {"server_label": server_label, "tools": [], "error": error_msg}


class ToolRegistry:
    """Registry for managing different tool loaders."""

    def __init__(self):
        """Initialize tool registry with available loaders."""
        self.loaders: Dict[str, ToolLoader] = {"mcp": MCPToolLoader()}

    async def load_all_tools(self, tools_config: Optional[List[Any]]) -> List[Any]:
        """Load all tools from configuration.

        Args:
            tools_config: List of tool configuration objects

        Returns:
            List of loaded toolset objects (excluding None values)
        """
        if not tools_config:
            logger.debug("No tools configuration provided")
            return []

        toolsets = []

        for tool_config in tools_config:
            # Determine tool type
            tool_type = getattr(tool_config, "type", None)

            if not tool_type:
                logger.warning(f"Tool configuration missing 'type' field: {tool_config}")
                continue

            # Get appropriate loader
            loader = self.loaders.get(tool_type)

            if not loader:
                logger.warning(f"No loader found for tool type '{tool_type}'")
                continue

            # Load the tool
            toolset = await loader.load_tools(tool_config)

            if toolset:
                toolsets.append(toolset)

        logger.debug(f"Loaded {len(toolsets)} toolsets from {len(tools_config)} configurations")
        return toolsets
