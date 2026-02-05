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

    async def load_tools(self, tool_config: MCPToolConfig) -> Optional[Any]:
        """Load MCP tools from configuration with optional name shortening.

        When gateway_slugs are provided, tool names are shortened by stripping
        the gateway prefix. This helps with:
        1. OpenAI's 64-character limit on function/tool names
        2. Improved accuracy in smaller LLMs with cleaner tool names

        Args:
            tool_config: MCP tool configuration

        Returns:
            MCPServerStreamableHTTP instance (possibly renamed) or None if server_url is missing
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

            # Get all gateway slugs (multiple connectors = multiple slugs)
            gateway_slugs = self._get_gateway_slugs(tool_config)

            if gateway_slugs:
                # Fetch tool list to get original names directly from mcp_server
                # (not via get_tool_list() which strips prefixes)
                tools_list = await mcp_server.list_tools()
                if tools_list:
                    original_names = [tool.name for tool in tools_list]

                    # Generate mapping: short_name -> original_name
                    # Try each slug to find matching prefix
                    name_map = {}
                    for original in original_names:
                        short = original  # Default: keep original if no prefix matches
                        for slug in gateway_slugs:
                            prefix = f"{slug}-"
                            if original.startswith(prefix):
                                short = original[len(prefix) :]
                                break  # Found matching prefix, stop searching
                        name_map[short] = original

                    # Update allowed_tool_names with SHORT names
                    tool_config.allowed_tool_names = list(name_map.keys())

                    logger.debug(
                        f"Stripped gateway prefixes from {len(name_map)} tools "
                        f"for server '{tool_config.server_label}' using {len(gateway_slugs)} slug(s)"
                    )

                    return mcp_server.renamed(name_map)

            logger.debug(
                f"Loaded MCP tool '{tool_config.server_label}' from {mcp_url} "
                f"with {len(tool_config.allowed_tools)} allowed tools"
            )

            return mcp_server

        except Exception as e:
            logger.error(f"Failed to load MCP tool '{tool_config.server_label}': {str(e)}")
            return None

    def _get_gateway_slugs(self, tool_config: MCPToolConfig) -> List[str]:
        """Extract all gateway slugs from tool config.

        When multiple connectors are registered, gateway_slugs contains:
        {connector1: slug1, connector2: slug2, ...}

        Returns all slugs so we can strip any matching prefix.

        Args:
            tool_config: MCP tool configuration

        Returns:
            List of gateway slugs
        """
        if tool_config.gateway_slugs:
            return list(tool_config.gateway_slugs.values())
        return []

    async def get_tool_list(self, tool_config: MCPToolConfig) -> Optional[Dict]:
        """Fetch the list of available tools from an MCP server.

        Creates its own MCP connection and strips gateway slugs from tool names.
        This is a self-contained method that can be called independently of load_tools().

        Args:
            tool_config: MCP tool configuration

        Returns:
            Dictionary with tools list (renamed if gateway_slugs present) or None on error
        """
        server_label = tool_config.server_label or "unknown"

        if not tool_config.server_url:
            logger.warning(f"Skipping MCP tool list '{server_label}': server_url is missing")
            return {"server_label": server_label, "tools": [], "error": "server_url is missing"}

        try:
            # Create fresh MCP server connection
            mcp_url = f"{self.base_url}servers/{tool_config.server_url}/mcp"
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            mcp_server = MCPServerStreamableHTTP(url=mcp_url, headers=headers if headers else None)

            # Fetch tool list
            tools_list = await mcp_server.list_tools()

            logger.debug(f"Retrieved {len(tools_list)} tools from MCP server '{server_label}'")

            # Get gateway slugs for name stripping
            gateway_slugs = self._get_gateway_slugs(tool_config)

            if gateway_slugs:
                # Strip gateway slugs from tool names
                # Create new Tool objects with renamed names
                renamed_tools = []
                for tool in tools_list:
                    short_name = tool.name
                    for slug in gateway_slugs:
                        prefix = f"{slug}-"
                        if tool.name.startswith(prefix):
                            short_name = tool.name[len(prefix) :]
                            break

                    # Create a modified copy with the short name
                    renamed_tool = tool.model_copy(update={"name": short_name})
                    renamed_tools.append(renamed_tool)

                logger.debug(f"Stripped gateway prefixes from {len(renamed_tools)} tools for '{server_label}'")
                return {"server_label": server_label, "tools": renamed_tools, "error": None}

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
