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

"""API routes for global connector operations — thin proxy to MCP Foundry."""

from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from budapp.commons import logging
from budapp.commons.constants import PermissionEnum
from budapp.commons.dependencies import get_current_active_user, get_session
from budapp.commons.exceptions import ClientException, MCPFoundryException
from budapp.commons.permission_handler import require_permissions
from budapp.commons.schemas import ErrorResponse, SuccessResponse
from budapp.user_ops.schemas import User

from .schemas import ClientsRequest, ConfigureConnectorRequest, OAuthCallbackRequest, TagExistingRequest, ToggleRequest
from .services import ConnectorService


logger = logging.get_logger(__name__)

connector_router = APIRouter(prefix="/connectors", tags=["connectors"])


# ═══════════════════════════════════════════════════════════════════════════════
# Admin routes — require ENDPOINT_MANAGE permission (same as prompt/connector ops)
# ═══════════════════════════════════════════════════════════════════════════════


@connector_router.get(
    "/registry",
    responses={
        status.HTTP_200_OK: {"description": "Successfully listed registry connectors"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
    description="Browse connectors from MCP Foundry registry",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def list_registry(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
    name: str = Query(None, description="Filter by name"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Browse available connectors from the MCP Foundry registry."""
    offset = (page - 1) * limit
    try:
        connectors, total = await ConnectorService().list_registry(name=name, offset=offset, limit=limit)
        return {
            "success": True,
            "message": "Registry connectors listed successfully",
            "connectors": connectors,
            "total_record": total,
            "page": page,
            "limit": limit,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to list registry connectors: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list registry connectors: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list registry connectors",
        ).to_http_response()


@connector_router.get(
    "/registry/{connector_id}",
    responses={
        status.HTTP_200_OK: {"description": "Successfully retrieved connector"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    description="Get a single connector from the MCP Foundry registry",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def get_registry_connector(
    connector_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get details of a single connector from the registry."""
    try:
        connector = await ConnectorService().get_registry_connector(connector_id)
        return {
            "success": True,
            "message": "Connector retrieved successfully",
            "connector": connector,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to get connector {connector_id}: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get connector {connector_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to get connector",
        ).to_http_response()


@connector_router.post(
    "/gateways",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_201_CREATED: {"description": "Gateway created successfully"},
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
    },
    description="Configure a global connector (create gateway with credentials)",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def configure_connector(
    request: ConfigureConnectorRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Admin: Configure a global connector by creating a gateway with credentials."""
    try:
        gateway = await ConnectorService().configure_connector(
            connector_id=request.connector_id,
            credentials=request.credentials,
        )
        return {
            "success": True,
            "message": "Connector configured successfully",
            "gateway": gateway,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to configure connector: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to configure connector: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to configure connector",
        ).to_http_response()


@connector_router.get(
    "/gateways",
    responses={
        status.HTTP_200_OK: {"description": "Successfully listed gateways"},
    },
    description="List all global gateways",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def list_gateways(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Admin: List all global gateways."""
    offset = (page - 1) * limit
    try:
        gateways, total = await ConnectorService().list_gateways(offset=offset, limit=limit)
        return {
            "success": True,
            "message": "Gateways listed successfully",
            "gateways": gateways,
            "total_record": total,
            "page": page,
            "limit": limit,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to list gateways: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list gateways: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list gateways",
        ).to_http_response()


@connector_router.get(
    "/gateways/{gateway_id}",
    responses={
        status.HTTP_200_OK: {"description": "Successfully retrieved gateway"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    description="Get gateway details with tools",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def get_gateway(
    gateway_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Admin: Get gateway details including tools."""
    try:
        gateway = await ConnectorService().get_gateway(gateway_id)
        return {
            "success": True,
            "message": "Gateway retrieved successfully",
            "gateway": gateway,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to get gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to get gateway",
        ).to_http_response()


@connector_router.put(
    "/gateways/{gateway_id}",
    responses={
        status.HTTP_200_OK: {"description": "Gateway updated successfully"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    description="Update a gateway",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def update_gateway(
    gateway_id: str,
    update_data: Dict[str, Any],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Admin: Update a gateway."""
    try:
        gateway = await ConnectorService().update_gateway(gateway_id, update_data)
        return {
            "success": True,
            "message": "Gateway updated successfully",
            "gateway": gateway,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to update gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to update gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update gateway",
        ).to_http_response()


@connector_router.delete(
    "/gateways/{gateway_id}",
    responses={
        status.HTTP_200_OK: {"description": "Gateway deleted successfully"},
    },
    description="Delete a gateway",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def delete_gateway(
    gateway_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Admin: Delete a gateway."""
    try:
        await ConnectorService().delete_gateway(gateway_id)
        return {
            "success": True,
            "message": "Gateway deleted successfully",
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to delete gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to delete gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete gateway",
        ).to_http_response()


# ═══════════════════════════════════════════════════════════════════════════════
# Admin routes — Configured connectors (tag-based)
# ═══════════════════════════════════════════════════════════════════════════════


@connector_router.get(
    "/configured",
    responses={
        status.HTTP_200_OK: {"description": "Successfully listed configured connectors"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
    description="List configured connectors enriched with registry metadata",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def list_configured(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
    client: str = Query(None, description="Filter by client tag (dashboard, chat)"),
    include_disabled: bool = Query(False, description="Include disabled gateways"),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    """Admin: List configured connectors with registry enrichment."""
    offset = (page - 1) * limit
    try:
        connectors, total = await ConnectorService().list_configured(
            client=client, include_disabled=include_disabled, offset=offset, limit=limit
        )
        return {
            "success": True,
            "message": "Configured connectors listed successfully",
            "connectors": connectors,
            "total_record": total,
            "page": page,
            "limit": limit,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to list configured connectors: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list configured connectors: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list configured connectors",
        ).to_http_response()


@connector_router.patch(
    "/configured/{gateway_id}/toggle",
    responses={
        status.HTTP_200_OK: {"description": "Gateway toggled successfully"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    description="Enable or disable a configured connector gateway",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def toggle_connector(
    gateway_id: str,
    request: ToggleRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Admin: Toggle a configured connector gateway on or off."""
    try:
        gateway = await ConnectorService().toggle_connector(gateway_id, request.enabled)
        return {
            "success": True,
            "message": f"Gateway {'enabled' if request.enabled else 'disabled'} successfully",
            "gateway": gateway,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to toggle gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to toggle gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to toggle gateway",
        ).to_http_response()


@connector_router.patch(
    "/configured/{gateway_id}/clients",
    responses={
        status.HTTP_200_OK: {"description": "Client tags updated successfully"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    description="Update which clients can access a configured connector gateway",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def update_connector_clients(
    gateway_id: str,
    request: ClientsRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Admin: Update client access tags for a configured connector gateway."""
    try:
        gateway = await ConnectorService().update_connector_clients(gateway_id, request.clients)
        return {
            "success": True,
            "message": "Client tags updated successfully",
            "gateway": gateway,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to update clients for gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to update clients for gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update client tags",
        ).to_http_response()


@connector_router.post(
    "/configured/{gateway_id}/tag",
    responses={
        status.HTTP_200_OK: {"description": "Tags added successfully"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    description="Backfill tags on an existing gateway",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_MANAGE])
async def tag_existing_gateway(
    gateway_id: str,
    request: TagExistingRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Admin: Add connector-id and standard tags to an existing gateway."""
    try:
        gateway = await ConnectorService().tag_existing_gateway(gateway_id, request.connector_id)
        return {
            "success": True,
            "message": "Gateway tagged successfully",
            "gateway": gateway,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to tag gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to tag gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to tag gateway",
        ).to_http_response()


# ═══════════════════════════════════════════════════════════════════════════════
# Public routes — no authentication required
# ═══════════════════════════════════════════════════════════════════════════════


@connector_router.get(
    "/oauth/public-callback",
    responses={
        status.HTTP_200_OK: {"description": "OAuth callback handled successfully"},
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
    },
    description="Public OAuth callback endpoint — no authentication required",
)
async def public_oauth_callback(
    code: str = Query(..., description="Authorization code from OAuth provider"),
    state: str = Query(..., description="State parameter for CSRF verification"),
) -> Dict[str, Any]:
    """Handle OAuth callback without requiring authentication.

    OAuth providers redirect here after user authorization. The endpoint proxies
    the code and state to MCP Foundry for token exchange.

    Security note: CSRF protection is delegated to MCP Foundry which validates
    the state parameter against the value it generated during initiate_oauth.
    The state is cryptographically signed by MCP Foundry and bound to the
    gateway + user session that initiated the flow.
    """
    if not code or not state:
        return ErrorResponse(
            code=status.HTTP_400_BAD_REQUEST,
            message="Missing required OAuth parameters (code, state)",
        ).to_http_response()
    try:
        result = await ConnectorService().handle_oauth_callback(code=code, state=state)
        return {
            "success": True,
            "message": "OAuth callback handled successfully",
            **result,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to handle public OAuth callback: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to handle public OAuth callback: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to handle OAuth callback",
        ).to_http_response()


# ═══════════════════════════════════════════════════════════════════════════════
# User routes — any authenticated user
# ═══════════════════════════════════════════════════════════════════════════════


@connector_router.get(
    "/available",
    responses={
        status.HTTP_200_OK: {"description": "Successfully listed available connectors"},
    },
    description="List enabled, dashboard-accessible configured connectors enriched with registry data",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def list_available_connectors(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """User: List enabled, dashboard-accessible connectors with registry enrichment."""
    offset = (page - 1) * limit
    try:
        connectors, total = await ConnectorService().list_configured(
            client="dashboard", include_disabled=False, offset=offset, limit=limit
        )
        return {
            "success": True,
            "message": "Available connectors listed successfully",
            "connectors": connectors,
            "total_record": total,
            "page": page,
            "limit": limit,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to list available connectors: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list available connectors: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list available connectors",
        ).to_http_response()


@connector_router.post(
    "/{gateway_id}/oauth/initiate",
    responses={
        status.HTTP_200_OK: {"description": "OAuth flow initiated"},
    },
    description="Start OAuth flow for a global connector",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def initiate_oauth(
    gateway_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """User: Start OAuth flow for a gateway."""
    try:
        result = await ConnectorService().initiate_oauth(gateway_id)
        return {
            "success": True,
            "message": "OAuth flow initiated",
            **result,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to initiate OAuth for gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to initiate OAuth for gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to initiate OAuth",
        ).to_http_response()


@connector_router.post(
    "/oauth/callback",
    responses={
        status.HTTP_200_OK: {"description": "OAuth callback handled successfully"},
    },
    description="Handle OAuth callback for a global connector",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def handle_oauth_callback(
    request: OAuthCallbackRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """User: Handle OAuth callback with authorization code."""
    try:
        result = await ConnectorService().handle_oauth_callback(code=request.code, state=request.state)
        return {
            "success": True,
            "message": "OAuth callback handled successfully",
            **result,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to handle OAuth callback: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to handle OAuth callback: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to handle OAuth callback",
        ).to_http_response()


@connector_router.post(
    "/{gateway_id}/fetch-tools",
    responses={
        status.HTTP_200_OK: {"description": "Tools fetched successfully"},
    },
    description="Fetch tools after OAuth completion",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def fetch_tools(
    gateway_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """User: Fetch tools after OAuth completion for a gateway."""
    try:
        result = await ConnectorService().fetch_tools(gateway_id)
        return {
            "success": True,
            "message": "Tools fetched successfully",
            **result,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to fetch tools for gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to fetch tools for gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to fetch tools",
        ).to_http_response()


@connector_router.get(
    "/{gateway_id}/tools",
    responses={
        status.HTTP_200_OK: {"description": "Successfully listed tools"},
    },
    description="List tools from a gateway",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def list_tools(
    gateway_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    """User: List tools from a gateway."""
    offset = (page - 1) * limit
    try:
        tools, total = await ConnectorService().list_tools(gateway_id=gateway_id, offset=offset, limit=limit)
        return {
            "success": True,
            "message": "Tools listed successfully",
            "tools": tools,
            "total_record": total,
            "page": page,
            "limit": limit,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to list tools for gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to list tools for gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list tools",
        ).to_http_response()


@connector_router.get(
    "/{gateway_id}/oauth/status",
    responses={
        status.HTTP_200_OK: {"description": "OAuth status retrieved"},
    },
    description="Check user's OAuth status for a gateway",
)
@require_permissions(permissions=[PermissionEnum.ENDPOINT_VIEW])
async def get_oauth_status(
    gateway_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """User: Check OAuth authorization status for a gateway."""
    try:
        result = await ConnectorService().get_oauth_status(gateway_id)
        return {
            "success": True,
            "message": "OAuth status retrieved",
            **result,
        }
    except (ClientException, MCPFoundryException) as e:
        logger.exception(f"Failed to get OAuth status for gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            message=str(e),
        ).to_http_response()
    except Exception as e:
        logger.exception(f"Failed to get OAuth status for gateway {gateway_id}: {e}")
        return ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to get OAuth status",
        ).to_http_response()
