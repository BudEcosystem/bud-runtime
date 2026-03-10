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

"""Shared utilities for MCP Foundry credential transformation and transport detection."""

from typing import Any, Dict, Union

from fastapi import status

from ..commons.exceptions import ClientException
from ..prompt_ops.schemas import HeadersCredentials, OAuthCredentials, OpenCredentials


# ─── OAuth constants ────────────────────────────────────────────────────────
OAUTH_REFRESH_THRESHOLD_SECONDS = 300


def detect_transport_from_url(url: str) -> str:
    """Detect transport type from connector URL.

    Returns "SSE" if URL ends with /sse, otherwise "STREAMABLEHTTP".
    """
    normalized_url = url.rstrip("/")
    if normalized_url.endswith("/sse"):
        return "SSE"
    return "STREAMABLEHTTP"


def transform_credentials_to_mcp_format(
    credentials: Union[OAuthCredentials, HeadersCredentials, OpenCredentials],
) -> Dict[str, Any]:
    """Transform credentials to MCP Foundry gateway payload format.

    Args:
        credentials: Typed credentials object

    Returns:
        Dictionary with auth configuration for MCP Foundry API

    Raises:
        ClientException: If unsupported auth type
    """
    auth_config: Dict[str, Any] = {}

    if isinstance(credentials, OAuthCredentials):
        oauth_config = {
            "grant_type": credentials.grant_type,
            "token_url": credentials.token_url,
            "authorization_url": credentials.authorization_url,
            "redirect_uri": credentials.redirect_uri,
            "token_management": {
                "store_tokens": True,
                "auto_refresh": True,
                "refresh_threshold_seconds": OAUTH_REFRESH_THRESHOLD_SECONDS,
            },
        }
        # Only include client credentials when provided (not DCR)
        if credentials.client_id:
            oauth_config["client_id"] = credentials.client_id
        if credentials.client_secret:
            oauth_config["client_secret"] = credentials.client_secret
        if credentials.scopes:
            oauth_config["scopes"] = credentials.scopes
        # Include DCR metadata for MCP Foundry
        if credentials.supports_dcr:
            oauth_config["supports_dcr"] = True
            if credentials.registration_url:
                oauth_config["registration_url"] = credentials.registration_url

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


def enrich_oauth_credentials_with_dcr(
    credentials: OAuthCredentials,
    connector_oauth_cfg: Dict[str, Any],
) -> None:
    """Enrich OAuth credentials with DCR info from connector registry.

    When the connector supports DCR and the user hasn't provided client credentials,
    sets supports_dcr=True and copies registration_url from the connector config.

    Args:
        credentials: OAuthCredentials to enrich (mutated in-place)
        connector_oauth_cfg: The oauth_config dict from the connector registry
    """
    if connector_oauth_cfg.get("supports_dcr") and not credentials.client_id:
        credentials.supports_dcr = True
        credentials.registration_url = credentials.registration_url or connector_oauth_cfg.get("registration_url")
