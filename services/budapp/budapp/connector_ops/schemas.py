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

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from ..prompt_ops.schemas import HeadersCredentials, OAuthCredentials, OpenCredentials


class ConfigureConnectorRequest(BaseModel):
    """Admin request to configure a global connector (create gateway with credentials)."""

    connector_id: str = Field(..., description="Connector ID from MCP Foundry registry")
    credentials: Union[OAuthCredentials, HeadersCredentials, OpenCredentials] = Field(
        ..., description="Credentials matching connector's auth_type"
    )


class CreateCustomGatewayRequest(BaseModel):
    """Request to create a custom MCP gateway directly (bypassing registry)."""

    name: str = Field(..., min_length=1, max_length=255, description="Gateway name")
    url: str = Field(..., description="MCP server URL")
    description: Optional[str] = Field(None, max_length=1000, description="Gateway description")
    transport: Optional[str] = Field(None, description="SSE or STREAMABLEHTTP; auto-detected if omitted")
    auth_type: Literal["OAuth", "Headers", "Open"] = Field(
        default="Open", description="Auth type; used to validate credentials match"
    )
    credentials: Union[OAuthCredentials, HeadersCredentials, OpenCredentials] = Field(
        default_factory=OpenCredentials, description="Credentials matching auth type"
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("transport")
    @classmethod
    def validate_transport(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("SSE", "STREAMABLEHTTP"):
            raise ValueError("Transport must be SSE or STREAMABLEHTTP")
        return v

    @model_validator(mode="after")
    def validate_credentials_match_auth_type(self) -> "CreateCustomGatewayRequest":
        """Ensure the resolved credential type matches the declared auth_type."""
        expected_type = {
            "OAuth": OAuthCredentials,
            "Headers": HeadersCredentials,
            "Open": OpenCredentials,
        }
        expected_cls = expected_type[self.auth_type]
        if not isinstance(self.credentials, expected_cls):
            raise ValueError(
                f"credentials do not match auth_type '{self.auth_type}': "
                f"expected {expected_cls.__name__}, got {type(self.credentials).__name__}"
            )
        return self


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
