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

    async def list_tools(
        self, integration_type: str, offset: int = 0, limit: int = 10
    ) -> tuple[List[Dict[str, Any]], int]:
        """List tools for a specific integration type with pagination.

        Args:
            integration_type: The type of integration (e.g., 'github', 'slack')
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
                integration_type=integration_type,
                offset=offset,
                limit=limit,
            )

            # Prepare parameters for MCP Foundry API
            params = {
                "include_inactive": "false",
                # "tags": integration_type,  # TODO: uncomment this when MCP Foudry has tags
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

            logger.info(
                "Successfully fetched tools from MCP Foundry",
                integration_type=integration_type,
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
