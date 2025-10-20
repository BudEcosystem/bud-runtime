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
from typing import Any, Dict, List, Optional

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
        self.api_key = secrets_settings.mcp_foundry_api_key
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

    async def get_tool_by_id(self, tool_id: str) -> Dict[str, Any]:
        """Get a single tool by its ID.

        Args:
            tool_id: The ID of the tool to retrieve

        Returns:
            Dict[str, Any]: Tool data from MCP Foundry

        Raises:
            MCPFoundryException: If the API call fails or tool not found
        """
        try:
            logger.info(
                "Fetching tool from MCP Foundry",
                tool_id=tool_id,
            )

            # Make the API call
            response = await self._make_request(
                method="GET",
                endpoint=f"/tools/{tool_id}",
            )

            logger.info(
                "Successfully fetched tool from MCP Foundry",
                tool_id=tool_id,
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
    ) -> Dict[str, Any]:
        """Create a gateway in MCP Foundry.

        Args:
            name: Gateway name (format: budprompt_id:connector_id)
            url: MCP server URL from connector details
            transport: Transport type (SSE, stdio) - default SSE
            visibility: Gateway visibility (public, private) - default public

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
            )

            # Prepare request payload
            payload = {
                "name": name,
                "url": url,
                "transport": transport,
                "visibility": visibility,
            }

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
