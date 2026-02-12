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

"""Service layer for global connector operations — thin proxy to MCP Foundry."""

import asyncio
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import status

from ..commons import logging
from ..commons.constants import CONNECTOR_AUTH_CREDENTIALS_MAP, MCP_AUTH_TYPE_MAPPING, ConnectorAuthTypeEnum
from ..commons.exceptions import ClientException
from ..prompt_ops.schemas import HeadersCredentials, OAuthCredentials, OpenCredentials
from ..shared.mcp_foundry_service import mcp_foundry_service


logger = logging.get_logger(__name__)


def _detect_transport_from_url(url: str) -> str:
    """Detect transport type from connector URL."""
    normalized_url = url.rstrip("/")
    if normalized_url.endswith("/sse"):
        return "SSE"
    return "STREAMABLEHTTP"


def _extract_tag_value(tags: List[str], prefix: str) -> Optional[str]:
    """Extract the value portion from a tag matching `prefix:value`."""
    for tag in tags:
        if tag.startswith(f"{prefix}:"):
            return tag[len(prefix) + 1 :]
    return None


def _transform_credentials_to_mcp_format(
    credentials: Union[OAuthCredentials, HeadersCredentials, OpenCredentials],
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
        oauth_config = {
            "grant_type": credentials.grant_type,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "token_url": credentials.token_url,
            "authorization_url": credentials.authorization_url,
            "redirect_uri": credentials.redirect_uri,
            "token_management": {
                "store_tokens": True,
                "auto_refresh": True,
                "refresh_threshold_seconds": 300,
            },
        }
        if credentials.scopes:
            oauth_config["scopes"] = credentials.scopes

        auth_config["auth_type"] = "oauth"
        auth_config["oauth_config"] = oauth_config

        if credentials.passthrough_headers:
            auth_config["passthrough_headers"] = credentials.passthrough_headers

    elif isinstance(credentials, HeadersCredentials):
        auth_config["auth_type"] = "authheaders"
        auth_config["auth_headers"] = credentials.auth_headers
        auth_config["oauth_grant_type"] = "client_credentials"
        auth_config["oauth_store_tokens"] = True
        auth_config["oauth_auto_refresh"] = True

        if credentials.passthrough_headers:
            auth_config["passthrough_headers"] = credentials.passthrough_headers

    elif isinstance(credentials, OpenCredentials):
        auth_config["oauth_grant_type"] = "client_credentials"
        auth_config["oauth_store_tokens"] = True
        auth_config["oauth_auto_refresh"] = True

        if credentials.passthrough_headers:
            auth_config["passthrough_headers"] = credentials.passthrough_headers

    else:
        raise ClientException(
            message=f"Unsupported credential type: {type(credentials).__name__}",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return auth_config


class ConnectorService:
    """Service for global connector operations — thin proxy to MCP Foundry."""

    # ─── Admin: Registry ─────────────────────────────────────────────────

    async def list_registry(
        self,
        name: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List available connectors from MCP Foundry registry."""
        connectors, total = await mcp_foundry_service.list_connectors(
            show_registered_only=False,
            show_available_only=True,
            name=name,
            offset=offset,
            limit=limit,
        )
        # Enrich each connector with credential_schema based on auth_type
        for c in connectors:
            auth_type_str = c.get("auth_type", "Open")
            auth_type = MCP_AUTH_TYPE_MAPPING.get(auth_type_str, ConnectorAuthTypeEnum.OPEN)
            c["credential_schema"] = CONNECTOR_AUTH_CREDENTIALS_MAP.get(auth_type, [])
        return connectors, total

    async def get_registry_connector(self, connector_id: str) -> Dict[str, Any]:
        """Get a single connector from the registry."""
        return await mcp_foundry_service.get_connector_by_id(connector_id)

    # ─── Admin: Gateway CRUD ─────────────────────────────────────────────

    async def configure_connector(
        self,
        connector_id: str,
        credentials: Union[OAuthCredentials, HeadersCredentials, OpenCredentials],
    ) -> Dict[str, Any]:
        """Configure a global connector by creating a gateway with credentials.

        1. Fetch connector details from registry
        2. Validate credentials match auth_type
        3. Transform creds to MCP format
        4. Create gateway in MCP Foundry
        """
        # 1. Fetch connector details
        connector = await mcp_foundry_service.get_connector_by_id(connector_id)

        # 2. Validate credentials match auth_type
        raw_auth_type = connector.get("auth_type", "")
        auth_type = MCP_AUTH_TYPE_MAPPING.get(raw_auth_type)

        if auth_type == ConnectorAuthTypeEnum.OAUTH and not isinstance(credentials, OAuthCredentials):
            raise ClientException(
                message=f"Connector '{connector_id}' requires OAuth credentials",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        elif auth_type == ConnectorAuthTypeEnum.HEADERS and not isinstance(credentials, HeadersCredentials):
            raise ClientException(
                message=f"Connector '{connector_id}' requires Headers credentials",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        elif auth_type == ConnectorAuthTypeEnum.OPEN and not isinstance(credentials, OpenCredentials):
            raise ClientException(
                message=f"Connector '{connector_id}' requires Open credentials",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Transform credentials
        auth_config = _transform_credentials_to_mcp_format(credentials)

        # 4. Create gateway — use connector name as gateway name, attach tags
        connector_name = connector.get("name", connector_id)
        gateway_name = connector_name
        connector_url = connector.get("url", "")
        transport = _detect_transport_from_url(connector_url)

        tags = [
            f"connector-id:{connector_id}",
            "source:budapp",
            "client:dashboard",
            "client:chat",
        ]

        gateway_response = await mcp_foundry_service.create_gateway(
            name=gateway_name,
            url=connector_url,
            transport=transport,
            visibility="public",
            auth_config=auth_config,
            tags=tags,
        )

        logger.info(
            "Created global gateway for connector",
            connector_id=connector_id,
            gateway_id=gateway_response.get("id", gateway_response.get("gateway_id")),
        )

        return gateway_response

    async def list_gateways(self, offset: int = 0, limit: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """List all gateways."""
        return await mcp_foundry_service.list_gateways(offset=offset, limit=limit)

    async def get_gateway(self, gateway_id: str) -> Dict[str, Any]:
        """Get a gateway by ID."""
        return await mcp_foundry_service.get_gateway_by_id(gateway_id)

    async def update_gateway(self, gateway_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a gateway."""
        return await mcp_foundry_service.update_gateway(gateway_id, update_data)

    async def delete_gateway(self, gateway_id: str) -> Dict[str, Any]:
        """Delete a gateway."""
        return await mcp_foundry_service.delete_gateway(gateway_id)

    # ─── User: OAuth & Tools ─────────────────────────────────────────────

    async def initiate_oauth(self, gateway_id: str) -> Dict[str, Any]:
        """Initiate OAuth flow for a gateway."""
        return await mcp_foundry_service.initiate_oauth(gateway_id)

    async def handle_oauth_callback(self, code: str, state: str) -> Dict[str, Any]:
        """Handle OAuth callback."""
        return await mcp_foundry_service.handle_oauth_callback(code, state)

    async def get_oauth_status(self, gateway_id: str) -> Dict[str, Any]:
        """Get OAuth status for a gateway."""
        return await mcp_foundry_service.get_oauth_status(gateway_id)

    async def fetch_tools(self, gateway_id: str) -> Dict[str, Any]:
        """Fetch tools after OAuth completion."""
        return await mcp_foundry_service.fetch_tools_after_oauth(gateway_id)

    async def list_tools(self, gateway_id: str, offset: int = 0, limit: int = 100) -> Tuple[List[Dict[str, Any]], int]:
        """List tools scoped to a specific gateway via get_gateway_by_id."""
        gateway = await mcp_foundry_service.get_gateway_by_id(gateway_id)
        tools = gateway.get("tools", [])
        total = len(tools)
        paginated = tools[offset : offset + limit]
        return paginated, total

    # ─── Configured Connectors (tag-based) ──────────────────────────────

    async def list_configured(
        self,
        client: Optional[str] = None,
        include_disabled: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List gateways that have a connector-id:* tag, enriched with registry data."""
        # 1. Fetch all gateways from MCP Foundry
        gateways, _ = await mcp_foundry_service.list_gateways(offset=0, limit=500)

        # 2. Filter: only gateways with a connector-id:* tag
        configured: List[Tuple[Dict[str, Any], str]] = []
        for gw in gateways:
            tags = gw.get("tags", [])
            connector_id = _extract_tag_value(tags, "connector-id")
            if not connector_id:
                continue
            if not include_disabled and not gw.get("enabled", True):
                continue
            if client and f"client:{client}" not in tags:
                continue
            configured.append((gw, connector_id))

        # 3. Single registry call → build lookup map (replaces N sequential get_connector_by_id calls)
        unique_ids = {cid for _, cid in configured}
        registry_map: Dict[str, Optional[Dict[str, Any]]] = {}
        if unique_ids:
            try:
                all_connectors, _ = await mcp_foundry_service.list_connectors(
                    show_registered_only=False, show_available_only=True, offset=0, limit=500
                )
                for c in all_connectors:
                    cid = c.get("id")
                    if cid in unique_ids:
                        registry_map[cid] = c
            except Exception:
                logger.warning("Failed to fetch registry connectors for enrichment")
            # Ensure all IDs have an entry (None for missing)
            for cid in unique_ids:
                registry_map.setdefault(cid, None)

        # 4. Fetch tool counts and OAuth status in parallel
        async def _tool_count(gw_id: str) -> Tuple[str, int]:
            try:
                detail = await mcp_foundry_service.get_gateway_by_id(gw_id)
                return gw_id, len(detail.get("tools", []))
            except Exception:
                return gw_id, 0

        async def _oauth_connected(gw_id: str) -> Tuple[str, bool]:
            try:
                oauth_status = await mcp_foundry_service.get_oauth_status(gw_id)
                return gw_id, bool(
                    oauth_status.get("oauth_enabled")
                    or oauth_status.get("connected")
                    or oauth_status.get("authorized")
                )
            except Exception:
                return gw_id, False

        gw_ids = [gw.get("id") for gw, _ in configured]
        tool_results, oauth_results = await asyncio.gather(
            asyncio.gather(*[_tool_count(gid) for gid in gw_ids]),
            asyncio.gather(*[_oauth_connected(gid) for gid in gw_ids]),
        )
        tool_count_map: Dict[str, int] = dict(tool_results)
        oauth_map: Dict[str, bool] = dict(oauth_results)

        # 5. Build enriched response
        results = []
        for gw, connector_id in configured:
            registry = registry_map.get(connector_id) or {}
            gw_id = gw.get("id")
            results.append(
                {
                    "id": gw_id,
                    "gateway_id": gw_id,
                    "connector_id": connector_id,
                    "name": gw.get("name", registry.get("name", connector_id)),
                    "enabled": gw.get("enabled", True),
                    "tags": gw.get("tags", []),
                    "icon": registry.get("logo_url"),
                    "description": registry.get("description"),
                    "category": registry.get("category"),
                    "auth_type": registry.get("auth_type"),
                    "documentation_url": registry.get("documentation_url"),
                    "tool_count": tool_count_map.get(gw_id, 0),
                    "oauth_connected": oauth_map.get(gw_id, False),
                }
            )

        total = len(results)
        paginated = results[offset : offset + limit]
        return paginated, total

    async def toggle_connector(self, gateway_id: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable a configured connector gateway."""
        return await mcp_foundry_service.update_gateway(gateway_id, {"enabled": enabled})

    async def update_connector_clients(self, gateway_id: str, clients: List[str]) -> Dict[str, Any]:
        """Update which clients (dashboard, chat) can access a gateway."""
        gateway = await mcp_foundry_service.get_gateway_by_id(gateway_id)
        current_tags = gateway.get("tags", [])
        # Remove existing client:* tags, add new ones
        new_tags = [t for t in current_tags if not t.startswith("client:")]
        new_tags.extend(f"client:{c}" for c in clients)
        return await mcp_foundry_service.update_gateway(gateway_id, {"tags": new_tags})

    async def tag_existing_gateway(self, gateway_id: str, connector_id: str) -> Dict[str, Any]:
        """Backfill tags on an existing gateway that was created before tag support."""
        gateway = await mcp_foundry_service.get_gateway_by_id(gateway_id)
        current_tags = gateway.get("tags", [])
        new_tags = list(
            set(current_tags)
            | {
                f"connector-id:{connector_id}",
                "source:budapp",
                "client:dashboard",
                "client:chat",
            }
        )
        return await mcp_foundry_service.update_gateway(gateway_id, {"tags": new_tags})
