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

"""Service class for interacting with MCP Foundry API."""

import asyncio
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import aiohttp

from budapp.commons import logging
from budapp.commons.config import app_settings, secrets_settings
from budapp.commons.exceptions import MCPFoundryException
from budapp.shared.singleton import SingletonMeta


logger = logging.get_logger(__name__)


class MCPFoundryService(metaclass=SingletonMeta):
    """Singleton service for MCP Foundry API interactions.

    This service provides methods to interact with the MCP Foundry API,
    handling authentication, retries, and error management.
    """

    def __init__(self):
        """Initialize the MCP Foundry service."""
        self.base_url = str(app_settings.mcp_foundry_base_url).rstrip("/")
        self.api_key = app_settings.mcp_foundry_api_key
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.max_retries = 3
        self.retry_delay = 1  # seconds

        # Initialize session as None, will be created on demand
        self._session: Optional[aiohttp.ClientSession] = None

        logger.debug(
            "MCP Foundry service initialized",
            base_url=self.base_url,
            has_api_key=bool(self.api_key),
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session.

        Returns:
            aiohttp.ClientSession: The HTTP session for making requests.
        """
        if self._session is None or self._session.closed:
            # Create connector with SSL disabled for localhost/HTTP connections
            connector = None
            if self.base_url.startswith("http://"):
                connector = aiohttp.TCPConnector(ssl=False)

            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                connector=connector,
            )
        return self._session

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request to MCP Foundry API with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON body data
            headers: Additional headers

        Returns:
            Dict[str, Any]: Response data

        Raises:
            MCPFoundryException: If the request fails after retries
        """
        url = f"{self.base_url}{endpoint}"

        # Prepare headers
        request_headers = headers or {}
        if self.api_key:
            request_headers["Authorization"] = f"Bearer {self.api_key}"

        last_exception = None

        for attempt in range(self.max_retries):
            try:
                session = await self._get_session()

                logger.debug(
                    "Making MCP Foundry request",
                    method=method,
                    url=url,
                    attempt=attempt + 1,
                    params=params,
                )

                async with session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=request_headers,
                ) as response:
                    # Check status code and raise exception if needed
                    if response.status == 401 or response.status == 403:
                        error_msg = f"Authentication failed for MCP Foundry: {response.status}"
                        logger.error(error_msg)
                        raise MCPFoundryException(error_msg, status_code=response.status)

                    elif response.status == 404:
                        error_msg = f"Resource not found in MCP Foundry: {endpoint}"
                        logger.error(error_msg)
                        raise MCPFoundryException(error_msg, status_code=404)

                    elif response.status >= 500:
                        error_msg = f"MCP Foundry server error: {response.status}"
                        logger.error(error_msg)
                        raise MCPFoundryException(error_msg, status_code=response.status)

                    elif response.status >= 400:
                        error_text = await response.text()
                        error_msg = f"MCP Foundry request failed: {response.status} - {error_text}"
                        logger.error(error_msg)
                        raise MCPFoundryException(error_msg, status_code=response.status)

                    # Success - parse response
                    data = await response.json()

                    logger.debug(
                        "MCP Foundry request successful",
                        method=method,
                        url=url,
                        status=response.status,
                    )

                    return data

            except aiohttp.ClientConnectionError as e:
                last_exception = e
                error_msg = f"Connection error to MCP Foundry: {str(e)}"
                logger.warning(
                    error_msg,
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                )

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue

            except aiohttp.ClientError as e:
                last_exception = e
                error_msg = f"HTTP client error with MCP Foundry: {str(e)}"
                logger.error(error_msg)
                raise MCPFoundryException(error_msg, status_code=500)

            except Exception as e:
                if isinstance(e, MCPFoundryException):
                    raise
                last_exception = e
                error_msg = f"Unexpected error with MCP Foundry: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise MCPFoundryException(error_msg, status_code=500)

        # All retries exhausted
        error_msg = f"Failed to connect to MCP Foundry after {self.max_retries} attempts: {str(last_exception)}"
        logger.error(error_msg)
        raise MCPFoundryException(error_msg, status_code=503)

    async def list_tools(self, server_id: str, offset: int = 0, limit: int = 10) -> tuple[List[Dict[str, Any]], int]:
        """List tools for a specific server (gateway).

        Args:
            server_id: MANDATORY - The gateway/server ID to filter tools
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            Tuple of (list of tools, total count)

        Raises:
            MCPFoundryException: If the API call fails
        """
        try:
            logger.info(
                "Fetching tools from MCP Foundry",
                server_id=server_id,
                offset=offset,
                limit=limit,
            )

            # Prepare parameters for MCP Foundry API
            params = {
                "include_inactive": "false",
                "server_id": server_id,
            }

            # Make the API call
            response = await self._make_request(
                method="GET",
                endpoint="/tools/",
                params=params,
            )

            # Handle response - could be a dict with data and cursor or just a list
            if isinstance(response, dict):
                # Response has pagination info
                tools = response.get("data", response.get("items", response.get("tools", [])))
            else:
                # Response is just a list of tools
                tools = response if isinstance(response, list) else []

            # Apply offset/limit pagination locally
            paginated_tools = tools[offset : offset + limit]

            # Set total_count to 0 as MCP Foundry doesn't provide it
            # This avoids the while loop for fetching all pages
            total_count = 0

            logger.debug(
                "Successfully fetched tools from MCP Foundry",
                server_id=server_id,
                returned_count=len(paginated_tools),
                total_count=total_count,
            )

            return paginated_tools, total_count

        except MCPFoundryException:
            # Re-raise MCP Foundry exceptions as-is
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            error_msg = f"Unexpected error listing tools: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def get_tool_by_id(self, tool_id: Union[str, UUID]) -> Dict[str, Any]:
        """Get a single tool by its ID.

        Args:
            tool_id: The ID of the tool to retrieve (UUID or string)

        Returns:
            Dict[str, Any]: Tool data from MCP Foundry

        Raises:
            MCPFoundryException: If the API call fails or tool not found
        """
        try:
            # Convert UUID to hex string if needed
            tool_id_str = str(tool_id.hex) if isinstance(tool_id, UUID) else tool_id

            logger.debug(
                "Fetching tool from MCP Foundry",
                tool_id=tool_id_str,
            )

            # Make the API call
            response = await self._make_request(
                method="GET",
                endpoint=f"/tools/{tool_id_str}",
            )

            logger.debug(
                "Successfully fetched tool from MCP Foundry",
                tool_id=tool_id_str,
                tool_name=response.get("displayName", "Unknown"),
            )

            return response

        except MCPFoundryException:
            # Re-raise MCP Foundry exceptions as-is
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            error_msg = f"Unexpected error getting tool {tool_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def list_all_tools(
        self,
        cursor: Optional[str] = None,
        include_inactive: bool = False,
        tags: Optional[List[str]] = None,
        team_id: Optional[str] = None,
        visibility: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List all tools from MCP Foundry without server_id filter.

        Args:
            cursor: Pagination cursor
            include_inactive: Include inactive tools
            tags: Filter by tags
            team_id: Filter by team ID
            visibility: Filter by visibility

        Returns:
            Dict containing 'data' (list of tools) and 'next_cursor'

        Raises:
            MCPFoundryException: If the API call fails
        """
        try:
            logger.info(
                "Fetching all tools from MCP Foundry",
                cursor=cursor,
                include_inactive=include_inactive,
                tags=tags,
                team_id=team_id,
                visibility=visibility,
            )

            params: Dict[str, Any] = {
                "include_inactive": str(include_inactive).lower(),
            }

            if cursor:
                params["cursor"] = cursor
            if tags:
                params["tags"] = ",".join(tags)
            if team_id:
                params["team_id"] = team_id
            if visibility:
                params["visibility"] = visibility

            response = await self._make_request(
                method="GET",
                endpoint="/tools/",
                params=params,
            )

            logger.debug(
                "Successfully fetched all tools from MCP Foundry",
                has_data="data" in response if isinstance(response, dict) else False,
            )

            return response

        except MCPFoundryException:
            raise
        except Exception as e:
            error_msg = f"Unexpected error listing all tools: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def update_tool(
        self,
        tool_id: Union[str, UUID],
        update_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update a tool in MCP Foundry.

        Args:
            tool_id: The ID of the tool to update
            update_data: Dictionary of fields to update (in camelCase)

        Returns:
            Dict[str, Any]: Updated tool data

        Raises:
            MCPFoundryException: If the API call fails
        """
        try:
            tool_id_str = str(tool_id.hex) if isinstance(tool_id, UUID) else str(tool_id)

            logger.debug(
                "Updating tool in MCP Foundry",
                tool_id=tool_id_str,
                update_fields=list(update_data.keys()),
            )

            response = await self._make_request(
                method="PUT",
                endpoint=f"/tools/{tool_id_str}",
                json_data=update_data,
            )

            logger.debug(
                "Successfully updated tool in MCP Foundry",
                tool_id=tool_id_str,
            )

            return response

        except MCPFoundryException:
            raise
        except Exception as e:
            error_msg = f"Unexpected error updating tool {tool_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def delete_tool(
        self,
        tool_id: Union[str, UUID],
    ) -> Dict[str, Any]:
        """Delete a tool from MCP Foundry.

        Args:
            tool_id: The ID of the tool to delete

        Returns:
            Empty dict on success

        Raises:
            MCPFoundryException: If the API call fails (except 404)
        """
        try:
            tool_id_str = str(tool_id.hex) if isinstance(tool_id, UUID) else str(tool_id)

            logger.debug(f"Deleting tool {tool_id_str} from MCP Foundry")

            response = await self._make_request(
                method="DELETE",
                endpoint=f"/tools/{tool_id_str}",
            )

            logger.debug(f"Successfully deleted tool {tool_id_str}")
            return response

        except MCPFoundryException as e:
            if e.status_code == 404:
                logger.warning(f"Tool {tool_id} not found (already deleted)")
                return {}
            raise
        except Exception as e:
            error_msg = f"Unexpected error deleting tool {tool_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def list_connectors(
        self,
        show_registered_only: bool = False,
        show_available_only: bool = True,
        name: Optional[str] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> tuple[List[Dict[str, Any]], int]:
        """List connectors from MCP registry.

        Args:
            show_registered_only: Filter for registered servers only
            show_available_only: Filter for available servers only
            name: Filter by connector name
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            Tuple of (list of connectors, total count)

        Raises:
            MCPFoundryException: If the API call fails
        """
        try:
            logger.debug(
                "Fetching connectors from MCP Foundry",
                show_registered_only=show_registered_only,
                show_available_only=show_available_only,
                name=name,
                offset=offset,
                limit=limit,
            )

            params = {
                "show_registered_only": str(show_registered_only).lower(),
                "show_available_only": str(show_available_only).lower(),
                "limit": limit,
                "offset": offset,
            }

            # Add name filter if provided
            if name:
                params["name"] = name

            response = await self._make_request(
                method="GET",
                endpoint="/admin/mcp-registry/servers",
                params=params,
            )

            servers = response.get("servers", [])
            total = response.get("total", len(servers))

            logger.debug(
                "Successfully fetched connectors from MCP Foundry",
                total_count=total,
            )

            return servers, total

        except MCPFoundryException:
            raise
        except Exception as e:
            error_msg = f"Unexpected error listing connectors: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def get_connector_by_id(self, connector_id: str) -> Dict[str, Any]:
        """Get a single connector by its ID from MCP Foundry.

        Since the MCP Foundry API doesn't have a direct /connectors/{id} endpoint,
        this method fetches all connectors using pagination and searches for the
        matching connector ID.

        Args:
            connector_id: The connector ID to find (e.g., "github", "slack")

        Returns:
            Dict containing the connector data

        Raises:
            MCPFoundryException: If connector not found or API error occurs
        """
        try:
            logger.debug(f"Searching for connector with ID: {connector_id}")

            page_size = 100  # Fetch in batches of 100
            offset = 0
            total_checked = 0

            while True:
                # Fetch a page of connectors
                connectors, total = await self.list_connectors(
                    show_registered_only=False, show_available_only=True, offset=offset, limit=page_size
                )

                # Search for connector ID in this batch
                for connector in connectors:
                    if connector.get("id") == connector_id:
                        logger.debug(f"Found connector: {connector.get('name', connector_id)}")
                        return connector

                # Update counters
                total_checked += len(connectors)
                offset += page_size

                # Check if we've fetched all connectors
                if offset >= total or len(connectors) == 0:
                    break

                logger.debug(f"Connector not found in first {total_checked} connectors, checking more...")

            # Connector not found after checking all pages
            error_msg = f"Connector {connector_id} not found in {total_checked} available connectors"
            logger.error(error_msg)
            raise MCPFoundryException(error_msg, status_code=404)

        except MCPFoundryException:
            # Re-raise MCP Foundry exceptions as-is
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            error_msg = f"Unexpected error getting connector {connector_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def list_connectors_by_connector_ids(
        self,
        connector_ids: List[str],
        show_registered_only: bool = False,
        show_available_only: bool = True,
        name: Optional[str] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> tuple[List[Dict[str, Any]], int]:
        """List connectors from MCP registry filtered by connector IDs.

        Since the MCP Foundry API doesn't support filtering by connector IDs,
        this method fetches all connectors with pagination and filters them in-memory.

        Args:
            connector_ids: List of connector IDs to filter by
            show_registered_only: Filter for registered servers only
            show_available_only: Filter for available servers only
            name: Filter by connector name
            offset: Number of items to skip (applied to filtered results)
            limit: Maximum number of items to return (applied to filtered results)

        Returns:
            Tuple of (filtered and paginated list of connectors, total count of filtered connectors)

        Raises:
            MCPFoundryException: If the API call fails
        """
        try:
            logger.debug(
                f"Fetching connectors from MCP Foundry filtered by {len(connector_ids)} connector IDs",
                show_registered_only=show_registered_only,
                show_available_only=show_available_only,
                name=name,
            )

            # Step 1: Fetch ALL connectors from MCP Foundry with pagination
            all_connectors = []
            current_offset = 0
            page_limit = 100  # Fetch 100 at a time for efficiency

            while True:
                params = {
                    "show_registered_only": str(show_registered_only).lower(),
                    "show_available_only": str(show_available_only).lower(),
                    "limit": page_limit,
                    "offset": current_offset,
                }

                # Add name filter if provided
                if name:
                    params["name"] = name

                response = await self._make_request(
                    method="GET",
                    endpoint="/admin/mcp-registry/servers",
                    params=params,
                )

                servers = response.get("servers", [])
                total_available = response.get("total", 0)

                all_connectors.extend(servers)

                logger.debug(
                    f"Fetched page: offset={current_offset}, "
                    f"page_size={len(servers)}, "
                    f"total_fetched={len(all_connectors)}/{total_available}"
                )

                # Check if we've fetched all connectors
                current_offset += page_limit
                if current_offset >= total_available or len(servers) < page_limit:
                    break

            logger.debug(f"Fetched {len(all_connectors)} total connectors from MCP Foundry")

            # Step 2: Filter connectors by connector_ids
            connector_ids_set = set(connector_ids)  # Convert to set for O(1) lookup
            filtered_connectors = []

            for connector in all_connectors:
                connector_id = connector.get("id", "")
                if connector_id in connector_ids_set:
                    filtered_connectors.append(connector)

            total_filtered = len(filtered_connectors)

            logger.debug(
                f"Filtered to {total_filtered} connectors matching provided IDs out of {len(all_connectors)} total"
            )

            # Step 3: Apply offset and limit to filtered results
            paginated_connectors = filtered_connectors[offset : offset + limit]

            logger.debug(
                f"Returning {len(paginated_connectors)} connectors "
                f"(offset={offset}, limit={limit}, total={total_filtered})"
            )

            return paginated_connectors, total_filtered

        except MCPFoundryException:
            raise
        except Exception as e:
            error_msg = f"Unexpected error listing connectors by IDs: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def create_gateway(
        self,
        name: str,
        url: str,
        transport: str = "SSE",
        visibility: str = "public",
        auth_config: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a gateway in MCP Foundry.

        Args:
            name: Gateway name (format: budprompt_id:connector_id)
            url: MCP server URL from connector details
            transport: Transport type (SSE, stdio) - default SSE
            visibility: Gateway visibility (public, private) - default public
            auth_config: Optional authentication configuration (OAuth, Headers, etc.)
            tags: Optional list of tags to attach to the gateway

        Returns:
            Dict[str, Any]: Gateway creation response with gateway_id

        Raises:
            MCPFoundryException: If gateway creation fails
        """
        try:
            logger.debug(
                "Creating gateway in MCP Foundry",
                name=name,
                url=url,
                transport=transport,
                visibility=visibility,
                has_auth_config=auth_config is not None,
                tags=tags,
            )

            # Prepare request payload
            payload = {
                "name": name,
                "url": url,
                "transport": transport,
                "visibility": visibility,
            }

            # Add tags if provided
            if tags:
                payload["tags"] = tags

            # Merge auth_config if provided
            if auth_config:
                payload.update(auth_config)

            # Make the API call
            response = await self._make_request(
                method="POST",
                endpoint="/gateways",
                json_data=payload,
            )

            logger.debug(
                "Successfully created gateway in MCP Foundry",
                gateway_id=response.get("id", response.get("gateway_id", "Unknown")),
                name=name,
            )

            return response

        except MCPFoundryException:
            # Re-raise MCP Foundry exceptions as-is
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            error_msg = f"Unexpected error creating gateway {name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def get_gateway_by_id(self, gateway_id: str) -> Dict[str, Any]:
        """Get a gateway by ID from MCP Foundry.

        Returns gateway details including all associated tools in the 'tools' array.

        Args:
            gateway_id: The gateway ID to retrieve

        Returns:
            Dict containing gateway data with 'tools' array including:
                - id, name, url, transport, visibility
                - tools: List of tool objects with id, originalName, displayName, etc.

        Raises:
            MCPFoundryException: If gateway not found or request fails
        """
        try:
            logger.debug(f"Fetching gateway with ID: {gateway_id}")

            response = await self._make_request(
                method="GET",
                endpoint=f"/gateways/{gateway_id}",
            )

            logger.debug(f"Successfully retrieved gateway {gateway_id} with {len(response.get('tools', []))} tools")
            return response

        except MCPFoundryException:
            # Re-raise MCP Foundry exceptions as-is
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            error_msg = f"Unexpected error getting gateway {gateway_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def create_virtual_server(
        self,
        name: str,
        associated_tools: List[str],
        visibility: str = "public",
    ) -> Dict[str, Any]:
        """Create a virtual server in MCP Foundry.

        Args:
            name: Virtual server name (prompt_id)
            associated_tools: List of tool IDs
            visibility: Server visibility (default: "public")

        Returns:
            Dict[str, Any]: Virtual server creation response with id

        Raises:
            MCPFoundryException: If virtual server creation fails
        """
        try:
            logger.debug(
                "Creating virtual server in MCP Foundry",
                name=name,
                associated_tools=associated_tools,
                visibility=visibility,
            )

            # Prepare request payload
            payload = {
                "server": {
                    "id": None,
                    "name": name,
                    "associated_tools": associated_tools,
                    "visibility": visibility,
                }
            }

            # Make the API call
            response = await self._make_request(
                method="POST",
                endpoint="/servers",
                json_data=payload,
            )

            logger.debug(
                "Successfully created virtual server in MCP Foundry",
                virtual_server_id=response.get("id", "Unknown"),
                name=name,
            )

            return response

        except MCPFoundryException:
            # Re-raise MCP Foundry exceptions as-is
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            error_msg = f"Unexpected error creating virtual server {name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def update_virtual_server(
        self,
        server_id: str,
        associated_tools: List[str],
    ) -> Dict[str, Any]:
        """Update a virtual server's associated tools.

        Args:
            server_id: Virtual server ID
            associated_tools: List of tool IDs (replaces existing)

        Returns:
            Dict[str, Any]: Updated virtual server response

        Raises:
            MCPFoundryException: If virtual server update fails
        """
        try:
            logger.debug(
                "Updating virtual server in MCP Foundry",
                server_id=server_id,
                associated_tools=associated_tools,
            )

            # Prepare request payload
            payload = {
                "associated_tools": associated_tools,
            }

            # Make the API call
            response = await self._make_request(
                method="PUT",
                endpoint=f"/servers/{server_id}",
                json_data=payload,
            )

            logger.debug(
                "Successfully updated virtual server in MCP Foundry",
                server_id=server_id,
            )

            return response

        except MCPFoundryException:
            # Re-raise MCP Foundry exceptions as-is
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            error_msg = f"Unexpected error updating virtual server {server_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def list_gateways(
        self,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[List[Dict[str, Any]], int]:
        """List all gateways from MCP Foundry.

        Args:
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            Tuple of (list of gateways, total count)

        Raises:
            MCPFoundryException: If the API call fails
        """
        try:
            logger.debug(
                "Fetching gateways from MCP Foundry",
                offset=offset,
                limit=limit,
            )

            params = {
                "offset": offset,
                "limit": limit,
            }

            response = await self._make_request(
                method="GET",
                endpoint="/gateways",
                params=params,
            )

            if isinstance(response, dict):
                gateways = response.get("gateways", response.get("data", response.get("items", [])))
                total = response.get("total", len(gateways))
            else:
                gateways = response if isinstance(response, list) else []
                total = len(gateways)

            logger.debug(
                "Successfully fetched gateways from MCP Foundry",
                returned_count=len(gateways),
                total_count=total,
            )

            return gateways, total

        except MCPFoundryException:
            raise
        except Exception as e:
            error_msg = f"Unexpected error listing gateways: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def update_gateway(
        self,
        gateway_id: str,
        update_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update a gateway in MCP Foundry.

        Args:
            gateway_id: The gateway ID to update
            update_data: Dictionary of fields to update

        Returns:
            Dict[str, Any]: Updated gateway data

        Raises:
            MCPFoundryException: If the API call fails
        """
        try:
            logger.debug(
                "Updating gateway in MCP Foundry",
                gateway_id=gateway_id,
                update_fields=list(update_data.keys()),
            )

            response = await self._make_request(
                method="PUT",
                endpoint=f"/gateways/{gateway_id}",
                json_data=update_data,
            )

            logger.debug(
                "Successfully updated gateway in MCP Foundry",
                gateway_id=gateway_id,
            )

            return response

        except MCPFoundryException:
            raise
        except Exception as e:
            error_msg = f"Unexpected error updating gateway {gateway_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def delete_gateway(
        self,
        gateway_id: str,
    ) -> Dict[str, Any]:
        """Delete a gateway from MCP Foundry.

        When a gateway is deleted, MCP Foundry automatically removes
        all tools associated with this gateway from the virtual server.

        Args:
            gateway_id: The gateway ID to delete

        Returns:
            Response from MCP Foundry (may be empty dict on success)

        Raises:
            MCPFoundryException: If deletion fails (except 404 or 400 with "Gateway not found")
        """
        try:
            response = await self._make_request(
                method="DELETE",
                endpoint=f"/gateways/{gateway_id}",
            )
            logger.debug(f"Successfully deleted gateway {gateway_id}")
            return response

        except MCPFoundryException as e:
            # Handle both 404 and 400 with "Gateway not found" message
            if e.status_code == 404 or (e.status_code == 400 and "Gateway not found" in e.message):
                # Gateway already deleted or doesn't exist - this is okay
                logger.warning(f"Gateway {gateway_id} not found (already deleted): {e.message}")
                return {}
            raise

    async def delete_virtual_server(
        self,
        server_id: str,
    ) -> Dict[str, Any]:
        """Delete a virtual server from MCP Foundry.

        Args:
            server_id: The virtual server ID to delete

        Returns:
            Response from MCP Foundry (may be empty dict on success)

        Raises:
            MCPFoundryException: If deletion fails (except 404)
        """
        try:
            response = await self._make_request(
                method="DELETE",
                endpoint=f"/servers/{server_id}",
            )
            logger.debug(f"Successfully deleted virtual server {server_id}")
            return response

        except MCPFoundryException as e:
            # Handle both 404 and 400 with "Server not found" message
            if e.status_code == 404 or (e.status_code == 400 and "Server not found" in e.message):
                # Server already deleted or doesn't exist - this is okay
                logger.warning(f"Server {server_id} not found (already deleted): {e.message}")
                return {}
            raise

    async def list_virtual_servers(
        self,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[List[Dict[str, Any]], int]:
        """List virtual servers from MCP Foundry.

        Args:
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            Tuple of (list of virtual servers, total count)

        Raises:
            MCPFoundryException: If the API call fails
        """
        try:
            logger.debug(
                "Fetching virtual servers from MCP Foundry",
                offset=offset,
                limit=limit,
            )

            params = {
                "offset": offset,
                "limit": limit,
            }

            response = await self._make_request(
                method="GET",
                endpoint="/servers",
                params=params,
            )

            # Handle response - could be a dict with data or just a list
            if isinstance(response, dict):
                servers = response.get("servers", response.get("data", response.get("items", [])))
                total = response.get("total", len(servers))
            else:
                servers = response if isinstance(response, list) else []
                total = len(servers)

            logger.debug(
                "Successfully fetched virtual servers from MCP Foundry",
                returned_count=len(servers),
                total_count=total,
            )

            return servers, total

        except MCPFoundryException:
            raise
        except Exception as e:
            error_msg = f"Unexpected error listing virtual servers: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def get_virtual_server_by_id(self, server_id: str) -> Dict[str, Any]:
        """Get a virtual server by ID from MCP Foundry.

        Args:
            server_id: The virtual server ID to retrieve

        Returns:
            Dict containing virtual server data with tools

        Raises:
            MCPFoundryException: If server not found or request fails
        """
        try:
            logger.debug(f"Fetching virtual server with ID: {server_id}")

            response = await self._make_request(
                method="GET",
                endpoint=f"/servers/{server_id}",
            )

            logger.debug(f"Successfully retrieved virtual server {server_id}")
            return response

        except MCPFoundryException:
            raise
        except Exception as e:
            error_msg = f"Unexpected error getting virtual server {server_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def get_virtual_server_tools(
        self,
        server_id: str,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get tools for a virtual server from MCP Foundry.

        Args:
            server_id: The virtual server ID
            include_inactive: Whether to include inactive tools

        Returns:
            List of tools associated with the virtual server

        Raises:
            MCPFoundryException: If request fails
        """
        try:
            logger.debug(f"Fetching tools for virtual server {server_id}")

            response = await self._make_request(
                method="GET",
                endpoint=f"/servers/{server_id}/tools",
                params={"include_inactive": str(include_inactive).lower()},
            )

            # Response might be a list directly or wrapped in an object
            tools = response if isinstance(response, list) else response.get("tools", response.get("data", []))

            logger.debug(f"Successfully retrieved {len(tools)} tools for server {server_id}")
            return tools

        except MCPFoundryException:
            raise
        except Exception as e:
            error_msg = f"Unexpected error getting tools for server {server_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def initiate_oauth(self, gateway_id: str) -> Dict[str, Any]:
        """Initiate OAuth flow for a gateway.

        Args:
            gateway_id: The gateway ID to initiate OAuth for

        Returns:
            Dict containing:
                - authorization_url: URL to redirect user to
                - state: OAuth state parameter
                - expires_in: State expiration time
                - gateway_id: The gateway ID

        Raises:
            MCPFoundryException: If OAuth initiation fails
        """
        try:
            logger.debug(f"Initiating OAuth flow for gateway {gateway_id}")

            # Make the API call
            response = await self._make_request(
                method="POST",
                endpoint="/oauth/api/initiate",
                params={"gateway_id": gateway_id},
            )

            logger.debug(f"Successfully initiated OAuth for gateway {gateway_id}")
            return response

        except MCPFoundryException:
            # Re-raise MCP Foundry exceptions as-is
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            error_msg = f"Unexpected error initiating OAuth for gateway {gateway_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def get_oauth_status(self, gateway_id: str) -> Dict[str, Any]:
        """Get OAuth status for a gateway.

        Args:
            gateway_id: The gateway ID to check OAuth status for

        Returns:
            Dict containing:
                - oauth_enabled: Whether OAuth is enabled
                - grant_type: OAuth grant type
                - client_id: OAuth client ID
                - scopes: List of OAuth scopes
                - authorization_url: OAuth authorization URL
                - redirect_uri: OAuth redirect URI
                - message: Status message

        Raises:
            MCPFoundryException: If OAuth status check fails
        """
        try:
            logger.debug(f"Checking OAuth status for gateway {gateway_id}")

            # Make the API call - GET request
            response = await self._make_request(
                method="GET",
                endpoint=f"/oauth/status/{gateway_id}",
            )

            logger.debug(f"Successfully retrieved OAuth status for gateway {gateway_id}")
            return response

        except MCPFoundryException:
            # Re-raise MCP Foundry exceptions as-is
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            error_msg = f"Unexpected error checking OAuth status for gateway {gateway_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def fetch_tools_after_oauth(self, gateway_id: str) -> Dict[str, Any]:
        """Fetch tools after OAuth completion for a gateway.

        Args:
            gateway_id: The gateway ID to fetch tools for

        Returns:
            Dict containing:
                - success: Whether tool fetching was successful
                - message: Status message from MCP Foundry

        Raises:
            MCPFoundryException: If tool fetching fails
        """
        try:
            logger.debug(f"Fetching tools after OAuth for gateway {gateway_id}")

            # Make the API call - POST request
            response = await self._make_request(
                method="POST",
                endpoint=f"/oauth/fetch-tools/{gateway_id}",
            )

            logger.debug(f"Successfully fetched tools for gateway {gateway_id}")
            return response

        except MCPFoundryException:
            # Re-raise MCP Foundry exceptions as-is
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            error_msg = f"Unexpected error fetching tools for gateway {gateway_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def handle_oauth_callback(self, code: str, state: str) -> Dict[str, Any]:
        """Handle OAuth callback by forwarding to MCP Foundry.

        Args:
            code: Authorization code from OAuth provider
            state: State parameter from OAuth flow

        Returns:
            Dict containing:
                - success: Whether callback was successful
                - gateway_id: Gateway ID
                - user_id: User ID/email
                - expires_at: Token expiration timestamp
                - message: Status message

        Raises:
            MCPFoundryException: If OAuth callback fails
        """
        try:
            logger.debug("Handling OAuth callback")

            # Make the API call - POST request with query params
            response = await self._make_request(
                method="POST",
                endpoint="/oauth/api/callback",
                params={"code": code, "state": state},
            )

            logger.debug("OAuth callback handled successfully")
            return response

        except MCPFoundryException:
            # Re-raise MCP Foundry exceptions as-is
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            error_msg = f"Unexpected error handling OAuth callback: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def get_oauth_token_status(self, gateway_id: str, user_id: str) -> Dict[str, Any]:
        """Check if a user has an active OAuth token for a gateway.

        Args:
            gateway_id: The gateway ID to check token status for
            user_id: The user ID (email) to check

        Returns:
            Dict containing token status (connected, gateway_id, user_id,
            token_type, expires_at, is_expired, scopes, created_at, updated_at)

        Raises:
            MCPFoundryException: If the request fails
        """
        try:
            logger.debug(f"Checking OAuth token status for gateway {gateway_id}, user {user_id}")

            response = await self._make_request(
                method="GET",
                endpoint=f"/oauth/api/tokens/{gateway_id}",
                headers={"X-User-ID": user_id},
            )

            logger.debug(f"Successfully retrieved OAuth token status for gateway {gateway_id}")
            return response

        except MCPFoundryException:
            raise
        except Exception as e:
            error_msg = f"Unexpected error checking OAuth token status for gateway {gateway_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def revoke_oauth_token(self, gateway_id: str, user_id: str) -> Dict[str, Any]:
        """Revoke the current user's OAuth token for a gateway.

        Args:
            gateway_id: The gateway ID to revoke token for
            user_id: The user ID (email) whose token to revoke

        Returns:
            Dict containing revocation result (success, gateway_id, message)

        Raises:
            MCPFoundryException: If the request fails
        """
        try:
            logger.debug(f"Revoking OAuth token for gateway {gateway_id}, user {user_id}")

            response = await self._make_request(
                method="DELETE",
                endpoint=f"/oauth/api/tokens/{gateway_id}",
                headers={"X-User-ID": user_id},
            )

            logger.debug(f"Successfully revoked OAuth token for gateway {gateway_id}")
            return response

        except MCPFoundryException:
            raise
        except Exception as e:
            error_msg = f"Unexpected error revoking OAuth token for gateway {gateway_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def admin_revoke_oauth_token(self, gateway_id: str, user_email: str) -> Dict[str, Any]:
        """Admin: Revoke another user's OAuth token for a gateway.

        Args:
            gateway_id: The gateway ID to revoke token for
            user_email: The email of the user whose token to revoke

        Returns:
            Dict containing revocation result (success, gateway_id, message)

        Raises:
            MCPFoundryException: If the request fails
        """
        try:
            logger.debug(f"Admin revoking OAuth token for gateway {gateway_id}, user {user_email}")

            response = await self._make_request(
                method="DELETE",
                endpoint=f"/oauth/api/tokens/{gateway_id}/{user_email}",
            )

            logger.debug(f"Successfully admin-revoked OAuth token for gateway {gateway_id}, user {user_email}")
            return response

        except MCPFoundryException:
            raise
        except Exception as e:
            error_msg = f"Unexpected error admin-revoking OAuth token for gateway {gateway_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def _make_multipart_request(
        self,
        method: str,
        endpoint: str,
        data: aiohttp.FormData,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a multipart/form-data HTTP request to MCP Foundry API.

        Args:
            method: HTTP method (typically POST)
            endpoint: API endpoint path
            data: FormData object with file and other fields
            params: Query parameters

        Returns:
            Dict[str, Any]: Response data

        Raises:
            MCPFoundryException: If the request fails
        """
        url = f"{self.base_url}{endpoint}"

        request_headers = {}
        if self.api_key:
            request_headers["Authorization"] = f"Bearer {self.api_key}"

        last_exception = None

        for attempt in range(self.max_retries):
            try:
                session = await self._get_session()

                logger.debug(
                    "Making MCP Foundry multipart request",
                    method=method,
                    url=url,
                    attempt=attempt + 1,
                    params=params,
                )

                async with session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    headers=request_headers,
                ) as response:
                    if response.status == 401 or response.status == 403:
                        error_msg = f"Authentication failed for MCP Foundry: {response.status}"
                        logger.error(error_msg)
                        raise MCPFoundryException(error_msg, status_code=response.status)

                    elif response.status == 404:
                        error_msg = f"Resource not found in MCP Foundry: {endpoint}"
                        logger.error(error_msg)
                        raise MCPFoundryException(error_msg, status_code=404)

                    elif response.status >= 500:
                        error_msg = f"MCP Foundry server error: {response.status}"
                        logger.error(error_msg)
                        raise MCPFoundryException(error_msg, status_code=response.status)

                    elif response.status >= 400:
                        error_text = await response.text()
                        error_msg = f"MCP Foundry request failed: {response.status} - {error_text}"
                        logger.error(error_msg)
                        raise MCPFoundryException(error_msg, status_code=response.status)

                    data_response = await response.json()

                    logger.debug(
                        "MCP Foundry multipart request successful",
                        method=method,
                        url=url,
                        status=response.status,
                    )

                    return data_response

            except aiohttp.ClientConnectionError as e:
                last_exception = e
                error_msg = f"Connection error to MCP Foundry: {str(e)}"
                logger.warning(
                    error_msg,
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                )

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue

            except aiohttp.ClientError as e:
                last_exception = e
                error_msg = f"HTTP client error with MCP Foundry: {str(e)}"
                logger.error(error_msg)
                raise MCPFoundryException(error_msg, status_code=500)

            except Exception as e:
                if isinstance(e, MCPFoundryException):
                    raise
                last_exception = e
                error_msg = f"Unexpected error with MCP Foundry: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise MCPFoundryException(error_msg, status_code=500)

        error_msg = f"Failed to connect to MCP Foundry after {self.max_retries} attempts: {str(last_exception)}"
        logger.error(error_msg)
        raise MCPFoundryException(error_msg, status_code=503)

    async def create_tools_from_openapi_url(
        self,
        url: str,
        enhance_with_ai: bool = True,
    ) -> Dict[str, Any]:
        """Create tools from an OpenAPI specification URL.

        Args:
            url: URL to the OpenAPI specification (JSON or YAML)
            enhance_with_ai: Use AI to enhance tool descriptions

        Returns:
            Dict containing created gateway/tools info:
                - gateway_id: ID of the created gateway
                - tools: List of created tool objects

        Raises:
            MCPFoundryException: If tool creation fails
        """
        try:
            logger.info(
                "Creating tools from OpenAPI URL",
                url=url,
                enhance_with_ai=enhance_with_ai,
            )

            response = await self._make_request(
                method="POST",
                endpoint="/tools/openapi/url",
                json_data={
                    "url": url,
                    "enhance_with_ai": enhance_with_ai,
                },
            )

            logger.info(
                "Successfully created tools from OpenAPI URL",
                gateway_id=response.get("gateway_id", response.get("id")),
                tools_count=len(response.get("tools", [])),
            )

            return response

        except MCPFoundryException:
            raise
        except Exception as e:
            error_msg = f"Unexpected error creating tools from OpenAPI URL: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def create_tools_from_openapi_file(
        self,
        file_content: bytes,
        file_name: str,
        content_type: str = "application/json",
        enhance_with_ai: bool = True,
    ) -> Dict[str, Any]:
        """Create tools from an uploaded OpenAPI specification file.

        Args:
            file_content: Binary content of the OpenAPI file
            file_name: Original filename
            content_type: MIME type of the file
            enhance_with_ai: Use AI to enhance tool descriptions

        Returns:
            Dict containing created gateway/tools info

        Raises:
            MCPFoundryException: If tool creation fails
        """
        try:
            logger.info(
                "Creating tools from OpenAPI file",
                file_name=file_name,
                content_type=content_type,
                enhance_with_ai=enhance_with_ai,
            )

            form_data = aiohttp.FormData()
            form_data.add_field(
                "file",
                file_content,
                filename=file_name,
                content_type=content_type,
            )
            form_data.add_field("enhance_with_ai", str(enhance_with_ai).lower())

            response = await self._make_multipart_request(
                method="POST",
                endpoint="/tools/openapi/upload",
                data=form_data,
            )

            logger.info(
                "Successfully created tools from OpenAPI file",
                gateway_id=response.get("gateway_id", response.get("id")),
                tools_count=len(response.get("tools", [])),
            )

            return response

        except MCPFoundryException:
            raise
        except Exception as e:
            error_msg = f"Unexpected error creating tools from OpenAPI file: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def create_tools_from_api_docs_url(
        self,
        url: str,
        enhance_with_ai: bool = True,
    ) -> Dict[str, Any]:
        """Create tools from an API documentation URL.

        Args:
            url: URL to the API documentation page
            enhance_with_ai: Use AI to enhance tool descriptions

        Returns:
            Dict containing created gateway/tools info

        Raises:
            MCPFoundryException: If tool creation fails
        """
        try:
            logger.info(
                "Creating tools from API docs URL",
                url=url,
                enhance_with_ai=enhance_with_ai,
            )

            response = await self._make_request(
                method="POST",
                endpoint="/tools/api-docs/url",
                json_data={
                    "url": url,
                    "enhance_with_ai": enhance_with_ai,
                },
            )

            logger.info(
                "Successfully created tools from API docs URL",
                gateway_id=response.get("gateway_id", response.get("id")),
                tools_count=len(response.get("tools", [])),
            )

            return response

        except MCPFoundryException:
            raise
        except Exception as e:
            error_msg = f"Unexpected error creating tools from API docs URL: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def create_tools_from_api_docs_file(
        self,
        file_content: bytes,
        file_name: str,
        content_type: str = "text/plain",
        enhance_with_ai: bool = True,
    ) -> Dict[str, Any]:
        """Create tools from an uploaded API documentation file.

        Args:
            file_content: Binary content of the documentation file
            file_name: Original filename
            content_type: MIME type of the file
            enhance_with_ai: Use AI to enhance tool descriptions

        Returns:
            Dict containing created gateway/tools info

        Raises:
            MCPFoundryException: If tool creation fails
        """
        try:
            logger.info(
                "Creating tools from API docs file",
                file_name=file_name,
                content_type=content_type,
                enhance_with_ai=enhance_with_ai,
            )

            form_data = aiohttp.FormData()
            form_data.add_field(
                "file",
                file_content,
                filename=file_name,
                content_type=content_type,
            )
            form_data.add_field("enhance_with_ai", str(enhance_with_ai).lower())

            response = await self._make_multipart_request(
                method="POST",
                endpoint="/tools/api-docs/upload",
                data=form_data,
            )

            logger.info(
                "Successfully created tools from API docs file",
                gateway_id=response.get("gateway_id", response.get("id")),
                tools_count=len(response.get("tools", [])),
            )

            return response

        except MCPFoundryException:
            raise
        except Exception as e:
            error_msg = f"Unexpected error creating tools from API docs file: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise MCPFoundryException(error_msg, status_code=500)

    async def list_catalogue_servers(
        self,
        show_registered_only: bool = False,
        show_available_only: bool = True,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[List[Dict[str, Any]], int]:
        """List servers from Bud catalogue (MCP registry).

        This is a convenience wrapper around list_connectors for the
        tool creation workflow.

        Args:
            show_registered_only: Filter for registered servers only
            show_available_only: Filter for available servers only
            offset: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            Tuple of (list of servers, total count)

        Raises:
            MCPFoundryException: If the API call fails
        """
        return await self.list_connectors(
            show_registered_only=show_registered_only,
            show_available_only=show_available_only,
            offset=offset,
            limit=limit,
        )

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.debug("MCP Foundry service session closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# module-level instance for easy import
mcp_foundry_service = MCPFoundryService()
