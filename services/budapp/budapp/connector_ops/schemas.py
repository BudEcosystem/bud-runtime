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

"""Pydantic schemas for the global connector operations module."""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from ..prompt_ops.schemas import HeadersCredentials, OAuthCredentials, OpenCredentials


class ConfigureConnectorRequest(BaseModel):
    """Admin request to configure a global connector (create gateway with credentials)."""

    connector_id: str = Field(..., description="Connector ID from MCP Foundry registry")
    credentials: Union[OAuthCredentials, HeadersCredentials, OpenCredentials] = Field(
        ..., description="Credentials matching connector's auth_type"
    )


class OAuthCallbackRequest(BaseModel):
    """Request schema for handling OAuth callback."""

    code: str = Field(..., description="Authorization code from OAuth provider")
    state: str = Field(..., description="State parameter from OAuth flow")


class ToggleRequest(BaseModel):
    """Request to enable/disable a configured connector gateway."""

    enabled: bool = Field(..., description="Whether the gateway should be enabled")


class ClientsRequest(BaseModel):
    """Request to update which clients can access a configured connector gateway."""

    clients: List[str] = Field(
        default_factory=list,
        description="List of client identifiers (e.g. 'studio', 'prompt')",
    )


class TagExistingRequest(BaseModel):
    """Request to backfill tags on an existing gateway."""

    connector_id: str = Field(..., description="Registry connector ID to link to this gateway")
