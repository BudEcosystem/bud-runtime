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
import re
from contextlib import suppress
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

from fastapi import status

from ..commons import logging
from ..commons.config import app_settings
from ..commons.constants import CONNECTOR_AUTH_CREDENTIALS_MAP, MCP_AUTH_TYPE_MAPPING, ConnectorAuthTypeEnum
from ..commons.exceptions import ClientException, MCPFoundryException
from ..prompt_ops.schemas import HeadersCredentials, OAuthCredentials, OpenCredentials
from ..shared.mcp_foundry_service import mcp_foundry_service
from ..shared.mcp_foundry_utils import (
    OAUTH_REFRESH_THRESHOLD_SECONDS,
    detect_transport_from_url,
    enrich_oauth_credentials_with_dcr,
    transform_credentials_to_mcp_format,
)
from ..shared.redis_service import RedisService


logger = logging.get_logger(__name__)

# ─── Tag constants ──────────────────────────────────────────────────────────
TAG_PREFIX_CONNECTOR_ID = "connector-id"
TAG_PREFIX_CLIENT = "client"
TAG_PREFIX_SOURCE = "source"
TAG_SOURCE_BUDAPP = "source:budapp"
TAG_SOURCE_CUSTOM = "source:custom"
TAG_CLIENT_STUDIO = "client:studio"
TAG_CLIENT_PROMPT = "client:prompt"
DEFAULT_CLIENT_TAGS = [TAG_CLIENT_STUDIO, TAG_CLIENT_PROMPT]

# Legacy tag mapping: new client name → old tag value (for migration period)
_LEGACY_CLIENT_TAGS = {
    "studio": "client:dashboard",
    "prompt": "client:chat",
}

# ─── OAuth return_url helpers ───────────────────────────────────────────────
_RETURN_URL_TTL_SECONDS = 600  # 10 minutes
_RETURN_URL_REDIS_PREFIX = "oauth_return_url:"

_redis_service = RedisService()


def validate_return_url(url: str) -> str:
    """Validate a return URL against the allowed domains list.

    Enforces HTTP(S) scheme for all domains; HTTPS required for non-localhost.

    Raises:
        ClientException: If the URL is invalid or the domain is not allowed.
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ClientException(
            message="Invalid return_url: missing scheme or host",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Only allow http and https schemes (blocks javascript:, data:, etc.)
    if parsed.scheme not in ("http", "https"):
        raise ClientException(
            message="return_url must use HTTP or HTTPS scheme",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    hostname = parsed.hostname or ""
    allowed_raw = app_settings.oauth_return_url_allowed_domains
    allowed_domains = {d.strip().lower() for d in allowed_raw.split(",") if d.strip()}

    if hostname.lower() not in allowed_domains:
        raise ClientException(
            message=f"return_url domain '{hostname}' is not in the allowed list",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    localhost_hosts = {"localhost", "127.0.0.1"}
    if hostname.lower() not in localhost_hosts and parsed.scheme != "https":
        raise ClientException(
            message="return_url must use HTTPS for non-localhost domains",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return url


async def store_return_url(state: str, url: str) -> None:
    """Store a return URL in Redis keyed by OAuth state with TTL."""
    key = f"{_RETURN_URL_REDIS_PREFIX}{state}"
    with suppress(Exception):
        await _redis_service.set(key, url, ex=_RETURN_URL_TTL_SECONDS)


async def pop_return_url(state: str) -> Optional[str]:
    """Retrieve and remove the return URL for a given OAuth state from Redis.

    Returns None if not found or expired.
    """
    key = f"{_RETURN_URL_REDIS_PREFIX}{state}"
    try:
        value = await _redis_service.get(key)
        if value:
            with suppress(Exception):
                await _redis_service.delete(key)
            return value.decode("utf-8") if isinstance(value, bytes) else str(value)
    except Exception:
        pass
    return None


def _detect_transport_from_url(url: str) -> str:
    """Detect transport type from connector URL."""
    return detect_transport_from_url(url)


def _extract_tag_value(tags: List[str], prefix: str) -> Optional[str]:
    """Extract the value portion from a tag matching `prefix:value`."""
    for tag in tags:
        if tag.startswith(f"{prefix}:"):
            return tag[len(prefix) + 1 :]
    return None


_MCP_AUTH_TYPE_LABELS = {
    "oauth": "OAuth2.1",
    "authheaders": "Headers",
}


def _derive_auth_type(gw: Dict[str, Any]) -> str:
    """Derive a human-readable auth_type from the gateway detail."""
    # MCP Foundry returns authType (camelCase) at top level
    raw = gw.get("authType") or gw.get("auth_type") or ""
    return _MCP_AUTH_TYPE_LABELS.get(raw, "Open")


def _transform_credentials_to_mcp_format(
    credentials: Union[OAuthCredentials, HeadersCredentials, OpenCredentials],
) -> Dict[str, Any]:
    """Transform credentials to MCP Foundry gateway payload format."""
    return transform_credentials_to_mcp_format(credentials)


def _enrich_credential_schema(connector: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build credential_schema with defaults from the connector's oauth_config.

    MCP Foundry returns an ``oauth_config`` block on OAuth connectors containing
    provider-specific values such as ``token_url`` and ``authorize_url``.  This
    helper copies the hardcoded field definitions from
    ``CONNECTOR_AUTH_CREDENTIALS_MAP`` and injects those values as ``default``
    entries so the frontend can pre-populate the form.
    """
    auth_type_str = connector.get("auth_type", "Open")
    auth_type = MCP_AUTH_TYPE_MAPPING.get(auth_type_str, ConnectorAuthTypeEnum.OPEN)
    # Deep-copy so we never mutate the module-level constant
    base_schema = [dict(f) for f in CONNECTOR_AUTH_CREDENTIALS_MAP.get(auth_type, [])]

    oauth_cfg = connector.get("oauth_config") or {}
    if not oauth_cfg:
        return base_schema

    # Map oauth_config keys → credential_schema field names
    defaults_map: Dict[str, str] = {}
    if oauth_cfg.get("token_url"):
        defaults_map["token_url"] = oauth_cfg["token_url"]
    if oauth_cfg.get("authorize_url"):
        defaults_map["authorization_url"] = oauth_cfg["authorize_url"]
    if oauth_cfg.get("scopes"):
        scopes = oauth_cfg["scopes"]
        if isinstance(scopes, list):
            defaults_map["scopes"] = " ".join(scopes)
        elif isinstance(scopes, str):
            defaults_map["scopes"] = scopes

    # Check if connector supports DCR — make client_id/secret optional
    supports_dcr = oauth_cfg.get("supports_dcr", False)

    for field in base_schema:
        default_val = defaults_map.get(field["field"])
        if default_val:
            field["default"] = default_val
        # If DCR is supported, client_id and client_secret become optional
        if supports_dcr and field["field"] in ("client_id", "client_secret"):
            field["required"] = False
            field["placeholder"] = "Leave empty for auto-registration via DCR"

    return base_schema


class ConnectorService:
    """Service for global connector operations — thin proxy to MCP Foundry."""

    # ─── Admin: Registry ─────────────────────────────────────────────────

    async def list_registry(
        self,
        name: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
        user_token: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List available connectors from MCP Foundry registry."""
        connectors, total = await mcp_foundry_service.list_connectors(
            show_registered_only=False,
            show_available_only=True,
            name=name,
            offset=offset,
            limit=limit,
            auth_token=user_token,
        )
        # Enrich each connector with credential_schema (with defaults) and normalize logo_url → icon
        for c in connectors:
            c["credential_schema"] = _enrich_credential_schema(c)
            # Map logo_url to icon for frontend consistency
            if "logo_url" in c:
                c["icon"] = c.pop("logo_url")
        return connectors, total

    async def get_registry_connector(self, connector_id: str, user_token: Optional[str] = None) -> Dict[str, Any]:
        """Get a single connector from the registry."""
        connector = await mcp_foundry_service.get_connector_by_id(connector_id, auth_token=user_token)
        # Enrich with credential_schema (with defaults) and normalize logo_url → icon
        connector["credential_schema"] = _enrich_credential_schema(connector)
        if "logo_url" in connector:
            connector["icon"] = connector.pop("logo_url")
        return connector

    # ─── Admin: Gateway CRUD ─────────────────────────────────────────────

    async def configure_connector(
        self,
        connector_id: str,
        credentials: Union[OAuthCredentials, HeadersCredentials, OpenCredentials],
        user_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Configure a global connector by creating a gateway with credentials.

        1. Fetch connector details from registry
        2. Validate credentials match auth_type
        3. Transform creds to MCP format
        4. Create gateway in MCP Foundry
        """
        # 1. Fetch connector details
        connector = await mcp_foundry_service.get_connector_by_id(connector_id, auth_token=user_token)

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

        # For DCR-capable OAuth servers, enrich credentials with DCR info from registry
        if auth_type == ConnectorAuthTypeEnum.OAUTH and isinstance(credentials, OAuthCredentials):
            connector_oauth_cfg = connector.get("oauth_config") or {}
            enrich_oauth_credentials_with_dcr(credentials, connector_oauth_cfg)

        # 3. Transform credentials
        auth_config = _transform_credentials_to_mcp_format(credentials)

        # 4. Create gateway — use connector name as gateway name, attach tags
        connector_name = connector.get("name", connector_id)
        gateway_name = connector_name
        connector_url = connector.get("url", "")
        transport = _detect_transport_from_url(connector_url)

        tags = [
            f"{TAG_PREFIX_CONNECTOR_ID}:{connector_id}",
            TAG_SOURCE_BUDAPP,
            *DEFAULT_CLIENT_TAGS,
        ]

        gateway_response = await mcp_foundry_service.create_gateway(
            name=gateway_name,
            url=connector_url,
            transport=transport,
            visibility="public",
            auth_config=auth_config,
            tags=tags,
            auth_token=user_token,
        )

        logger.info(
            "Created global gateway for connector",
            connector_id=connector_id,
            gateway_id=gateway_response.get("id", gateway_response.get("gateway_id")),
        )

        return gateway_response

    async def create_custom_gateway(
        self,
        name: str,
        url: str,
        description: Optional[str] = None,
        transport: Optional[str] = None,
        credentials: Union[OAuthCredentials, HeadersCredentials, OpenCredentials, None] = None,
        user_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a custom MCP gateway directly (bypassing registry lookup).

        This allows users to connect to any MCP server by providing its URL,
        without requiring the server to be registered in the MCP Foundry registry.
        """
        if credentials is None:
            credentials = OpenCredentials()

        if transport is None:
            transport = _detect_transport_from_url(url)

        auth_config = _transform_credentials_to_mcp_format(credentials)

        tags = [TAG_SOURCE_CUSTOM, *DEFAULT_CLIENT_TAGS]

        gateway_response = await mcp_foundry_service.create_gateway(
            name=name,
            url=url,
            description=description,
            transport=transport,
            visibility="public",
            auth_config=auth_config,
            tags=tags,
            auth_token=user_token,
        )

        logger.info(
            "Created custom gateway",
            gateway_id=gateway_response.get("id", gateway_response.get("gateway_id")),
            name=name,
        )

        return gateway_response

    async def list_gateways(
        self, offset: int = 0, limit: int = 20, user_token: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List all gateways."""
        return await mcp_foundry_service.list_gateways(offset=offset, limit=limit, auth_token=user_token)

    async def get_gateway(self, gateway_id: str, user_token: Optional[str] = None) -> Dict[str, Any]:
        """Get a gateway by ID."""
        return await mcp_foundry_service.get_gateway_by_id(gateway_id, auth_token=user_token)

    async def update_gateway(
        self, gateway_id: str, update_data: Dict[str, Any], user_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update a gateway."""
        return await mcp_foundry_service.update_gateway(gateway_id, update_data, auth_token=user_token)

    async def delete_gateway(self, gateway_id: str, user_token: Optional[str] = None) -> Dict[str, Any]:
        """Delete a gateway."""
        return await mcp_foundry_service.delete_gateway(gateway_id, auth_token=user_token)

    # ─── User: OAuth & Tools ─────────────────────────────────────────────

    async def initiate_oauth(self, gateway_id: str, user_token: Optional[str] = None) -> Dict[str, Any]:
        """Initiate OAuth flow for a gateway."""
        return await mcp_foundry_service.initiate_oauth(gateway_id, auth_token=user_token)

    async def handle_oauth_callback(self, code: str, state: str, user_token: Optional[str] = None) -> Dict[str, Any]:
        """Handle OAuth callback and auto-fetch tools from the MCP server.

        After the token exchange succeeds, we trigger tool discovery so that
        the tool list is populated immediately rather than staying empty until
        a manual fetch-tools call.
        """
        result = await mcp_foundry_service.handle_oauth_callback(code, state, auth_token=user_token)

        gateway_id = result.get("gateway_id")
        if gateway_id and re.fullmatch(r"[0-9a-fA-F\-]{1,64}", gateway_id):
            try:
                await mcp_foundry_service.fetch_tools_after_oauth(gateway_id, auth_token=user_token)
                logger.info("Auto-fetched tools after OAuth", gateway_id=gateway_id)
            except (MCPFoundryException, Exception) as fetch_err:
                logger.warning(
                    "Failed to auto-fetch tools after OAuth",
                    gateway_id=gateway_id,
                    error=str(fetch_err),
                )
        elif gateway_id:
            logger.warning("Skipping auto-fetch: invalid gateway_id format", gateway_id=gateway_id)

        return result

    async def get_oauth_status(self, gateway_id: str, user_token: Optional[str] = None) -> Dict[str, Any]:
        """Get OAuth status for a gateway."""
        return await mcp_foundry_service.get_oauth_status(gateway_id, auth_token=user_token)

    async def fetch_tools(self, gateway_id: str, user_token: Optional[str] = None) -> Dict[str, Any]:
        """Fetch tools after OAuth completion."""
        return await mcp_foundry_service.fetch_tools_after_oauth(gateway_id, auth_token=user_token)

    async def get_oauth_token_status(
        self, gateway_id: str, user_id: str, user_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check if a user has an active OAuth token for a gateway."""
        return await mcp_foundry_service.get_oauth_token_status(gateway_id, user_id, auth_token=user_token)

    async def revoke_oauth_token(
        self, gateway_id: str, user_id: str, user_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Revoke the current user's OAuth token for a gateway."""
        return await mcp_foundry_service.revoke_oauth_token(gateway_id, user_id, auth_token=user_token)

    async def admin_revoke_oauth_token(
        self, gateway_id: str, user_email: str, user_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Admin: Revoke another user's OAuth token for a gateway."""
        return await mcp_foundry_service.admin_revoke_oauth_token(gateway_id, user_email, auth_token=user_token)

    async def list_tools(
        self, gateway_id: str, offset: int = 0, limit: int = 100, user_token: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List tools scoped to a specific gateway via get_gateway_by_id."""
        gateway = await mcp_foundry_service.get_gateway_by_id(gateway_id, auth_token=user_token)

        # Validate gateway is enabled and accessible to studio clients
        if not gateway.get("enabled", True):
            raise ClientException(
                message="Gateway is disabled",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        tags = gateway.get("tags", [])
        # Accept both new (client:studio) and legacy (client:dashboard) tags during migration
        legacy_studio_tag = _LEGACY_CLIENT_TAGS.get("studio")
        if tags and TAG_CLIENT_STUDIO not in tags and (not legacy_studio_tag or legacy_studio_tag not in tags):
            raise ClientException(
                message="Gateway is not accessible to the studio client",
                status_code=status.HTTP_403_FORBIDDEN,
            )

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
        user_token: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List gateways that have a connector-id:* tag, enriched with registry data."""
        # 1. Fetch all gateways from MCP Foundry
        gateways, _ = await mcp_foundry_service.list_gateways(offset=0, limit=500, auth_token=user_token)

        # 2. Filter: gateways with a connector-id:* tag or source:custom tag
        configured: List[Tuple[Dict[str, Any], Optional[str]]] = []
        for gw in gateways:
            tags = gw.get("tags", [])
            connector_id = _extract_tag_value(tags, TAG_PREFIX_CONNECTOR_ID)
            is_custom = TAG_SOURCE_CUSTOM in tags
            if not connector_id and not is_custom:
                continue
            if not include_disabled and not gw.get("enabled", True):
                continue
            if client:
                new_tag = f"{TAG_PREFIX_CLIENT}:{client}"
                legacy_tag = _LEGACY_CLIENT_TAGS.get(client)
                if new_tag not in tags and (not legacy_tag or legacy_tag not in tags):
                    continue
            configured.append((gw, connector_id))

        # 3. Single registry call → build lookup map (replaces N sequential get_connector_by_id calls)
        unique_ids = {cid for _, cid in configured if cid}
        registry_map: Dict[str, Optional[Dict[str, Any]]] = {}
        if unique_ids:
            try:
                all_connectors, _ = await mcp_foundry_service.list_connectors(
                    show_registered_only=False,
                    show_available_only=True,
                    offset=0,
                    limit=500,
                    auth_token=user_token,
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

        # 4. Fetch gateway details and OAuth status in parallel
        async def _gateway_detail(gw_id: str) -> Tuple[str, Dict[str, Any]]:
            try:
                detail = await mcp_foundry_service.get_gateway_by_id(gw_id, auth_token=user_token)
                return gw_id, detail
            except Exception:
                return gw_id, {}

        async def _oauth_connected(gw_id: str) -> Tuple[str, bool]:
            try:
                oauth_status = await mcp_foundry_service.get_oauth_status(gw_id, auth_token=user_token)
                return gw_id, bool(
                    oauth_status.get("oauth_enabled")
                    or oauth_status.get("connected")
                    or oauth_status.get("authorized")
                )
            except Exception:
                return gw_id, False

        gw_ids = [gw.get("id") for gw, _ in configured]
        detail_results, oauth_results = await asyncio.gather(
            asyncio.gather(*[_gateway_detail(gid) for gid in gw_ids]),
            asyncio.gather(*[_oauth_connected(gid) for gid in gw_ids]),
        )
        detail_map: Dict[str, Dict[str, Any]] = dict(detail_results)
        oauth_map: Dict[str, bool] = dict(oauth_results)

        # 5. Build enriched response
        results = []
        for gw, connector_id in configured:
            registry = registry_map.get(connector_id) or {} if connector_id else {}
            gw_id = gw.get("id")
            is_custom = TAG_SOURCE_CUSTOM in gw.get("tags", [])
            detail = detail_map.get(gw_id, {})
            results.append(
                {
                    "id": gw_id,
                    "gateway_id": gw_id,
                    "connector_id": connector_id,
                    "name": gw.get("name", registry.get("name", connector_id or "")),
                    "enabled": gw.get("enabled", True),
                    "tags": gw.get("tags", []),
                    "icon": registry.get("logo_url"),
                    "description": gw.get("description") if is_custom else registry.get("description"),
                    "category": "Custom" if is_custom else registry.get("category"),
                    "auth_type": _derive_auth_type(detail) if is_custom else registry.get("auth_type"),
                    "documentation_url": registry.get("documentation_url"),
                    "tool_count": len(detail.get("tools", [])),
                    "oauth_connected": oauth_map.get(gw_id, False),
                    "is_custom": is_custom,
                }
            )

        total = len(results)
        paginated = results[offset : offset + limit]
        return paginated, total

    async def toggle_connector(
        self, gateway_id: str, enabled: bool, user_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enable or disable a configured connector gateway."""
        return await mcp_foundry_service.update_gateway(gateway_id, {"enabled": enabled}, auth_token=user_token)

    async def update_connector_clients(
        self, gateway_id: str, clients: List[str], user_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update which clients (studio, prompt) can access a gateway."""
        gateway = await mcp_foundry_service.get_gateway_by_id(gateway_id, auth_token=user_token)
        current_tags = gateway.get("tags", [])
        # Remove existing client:* tags, add new ones
        new_tags = [t for t in current_tags if not t.startswith(f"{TAG_PREFIX_CLIENT}:")]
        new_tags.extend(f"{TAG_PREFIX_CLIENT}:{c}" for c in clients)
        return await mcp_foundry_service.update_gateway(gateway_id, {"tags": new_tags}, auth_token=user_token)

    async def tag_existing_gateway(
        self, gateway_id: str, connector_id: str, user_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Backfill tags on an existing gateway that was created before tag support."""
        gateway = await mcp_foundry_service.get_gateway_by_id(gateway_id, auth_token=user_token)
        current_tags = gateway.get("tags", [])
        new_tags = list(
            set(current_tags)
            | {
                f"{TAG_PREFIX_CONNECTOR_ID}:{connector_id}",
                TAG_SOURCE_BUDAPP,
                *DEFAULT_CLIENT_TAGS,
            }
        )
        return await mcp_foundry_service.update_gateway(gateway_id, {"tags": new_tags}, auth_token=user_token)
