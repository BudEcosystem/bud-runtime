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

"""Pydantic schemas for the prompt ops module."""

import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator, model_validator

from ..cluster_ops.schemas import ClusterResponse
from ..commons.constants import (
    ConnectorAuthTypeEnum,
    ModalityEnum,
    PromptStatusEnum,
    PromptTypeEnum,
    PromptVersionStatusEnum,
)
from ..commons.schemas import PaginatedSuccessResponse, SuccessResponse, Tag
from ..endpoint_ops.schemas import EndpointResponse
from ..model_ops.schemas import ModelResponse
from ..project_ops.schemas import ProjectResponse


class PromptFilter(BaseModel):
    """Filter schema for prompt list API."""

    name: str | None = None
    prompt_type: PromptTypeEnum | None = None
    project_id: UUID4 | None = None


class PromptVersionFilter(BaseModel):
    """Filter schema for prompt version list API."""

    version: int | None = None


class PromptListItem(BaseModel):
    """Schema for individual prompt item in list."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    description: str | None
    tags: list[dict] | None
    created_at: datetime
    modified_at: datetime
    prompt_type: str
    model_icon: str | None
    model_name: str
    default_version: int | None
    modality: list[str] | None
    status: str  # Endpoint status


class PromptListResponse(PaginatedSuccessResponse):
    """Prompt list response schema."""

    model_config = ConfigDict(extra="ignore")

    prompts: list[PromptListItem] = []


class PromptVersionListItem(BaseModel):
    """Schema for individual prompt version item in list."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    endpoint_name: str
    version: int
    created_at: datetime
    modified_at: datetime
    is_default_version: bool


class PromptVersionListResponse(PaginatedSuccessResponse):
    """Prompt version list response schema."""

    model_config = ConfigDict(extra="ignore")

    versions: list[PromptVersionListItem] = []


class PaginatedTagsResponse(PaginatedSuccessResponse):
    """Paginated tags response schema for prompts."""

    tags: list[Tag] = []


class ModelSettings(BaseModel):
    """Model settings for LLM configuration.

    Supports all OpenAI and BudEcosystem parameters. Parameters not in
    OpenAIModelSettings are automatically routed to extra_body.

    Standard OpenAI parameters:
        temperature: Controls randomness in the model's output (0-2)
        max_tokens: Maximum number of tokens to generate
        top_p: Controls diversity of the output (0-1)
        frequency_penalty: Penalizes frequently used tokens (-2 to 2)
        presence_penalty: Penalizes tokens based on presence in the text (-2 to 2)
        stop_sequences: List of sequences where the model will stop generating
        seed: Random seed for reproducibility
        timeout: Request timeout in seconds
        parallel_tool_calls: Allow parallel tool calls
        logprobs: Return token log probabilities
        logit_bias: Token likelihood modifications
        extra_headers: Additional HTTP headers

    BudEcosystem-specific parameters (auto-routed to extra_body):
        max_completion_tokens: Alternative to max_tokens (OpenAI compatibility)
        stream_options: Streaming configuration
        response_format: Output format control
        tool_choice: Tool selection strategy
        chat_template: Custom chat template
        chat_template_kwargs: Template parameters (e.g., {'enable_thinking': true})
        mm_processor_kwargs: Multi-modal processor parameters
        guided_json: JSON schema for guided generation
        guided_regex: Regex pattern for guided generation
        guided_choice: List of allowed values
        guided_grammar: Grammar for guided generation
        structural_tag: Structural generation tag
        guided_decoding_backend: Backend for guided decoding
        guided_whitespace_pattern: Whitespace pattern for guided generation
    """

    # Standard OpenAI-compatible parameters
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=2000, gt=0, description="Maximum tokens to generate")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0, description="Penalize repeated tokens")
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0, description="Penalize tokens based on presence")
    stop_sequences: List[str] = Field(default_factory=list, description="Stop generation sequences")
    seed: Optional[int] = Field(None, description="Random seed for reproducibility")

    # Additional pydantic-ai supported parameters
    timeout: Optional[float] = Field(None, description="Request timeout in seconds")
    parallel_tool_calls: Optional[bool] = Field(None, description="Allow parallel tool calls")
    logprobs: Optional[bool] = Field(None, description="Return token log probabilities")
    logit_bias: Optional[Dict[str, int]] = Field(None, description="Token likelihood modifications")
    extra_headers: Optional[Dict[str, str]] = Field(None, description="Additional HTTP headers")

    # BudEcosystem-specific parameters (will go to extra_body)
    max_completion_tokens: Optional[int] = Field(None, description="Alternative to max_tokens (OpenAI compatibility)")
    stream_options: Optional[Dict[str, Any]] = Field(None, description="Streaming configuration")
    response_format: Optional[Dict[str, Any]] = Field(None, description="Output format control")
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Field(None, description="Tool selection strategy")

    # Template customization
    chat_template: Optional[str] = Field(None, description="Custom chat template")
    chat_template_kwargs: Optional[Dict[str, Any]] = Field(
        None, description="Template parameters (e.g., {'enable_thinking': true})"
    )
    mm_processor_kwargs: Optional[Dict[str, Any]] = Field(None, description="Multi-modal processor parameters")

    # Guided generation parameters
    guided_json: Optional[Dict[str, Any]] = Field(None, description="JSON schema for guided generation")
    guided_regex: Optional[str] = Field(None, description="Regex pattern for guided generation")
    guided_choice: Optional[List[str]] = Field(None, description="List of allowed values")
    guided_grammar: Optional[str] = Field(None, description="Grammar for guided generation")
    structural_tag: Optional[str] = Field(None, description="Structural generation tag")
    guided_decoding_backend: Optional[str] = Field(None, description="Backend for guided decoding")
    guided_whitespace_pattern: Optional[str] = Field(None, description="Whitespace pattern for guided generation")


class Message(BaseModel):
    """Message structure for prompt execution.

    Attributes:
        role: The role of the message sender (system, developer, user, or assistant)
        content: The content of the message
    """

    role: Literal["system", "developer", "user", "assistant"] = Field(default="user")
    content: str = Field(..., min_length=1)


class PromptSchemaConfig(BaseModel):
    """Schema for prompt configuration stored in prompt_schema field."""

    """Request model for prompt execution.

    Supports both structured and unstructured inputs/outputs:
    - If input_schema is provided: input_data should be a Dict matching the schema
    - If input_schema is None: input_data should be a string (unstructured)
    - If output_schema is provided: output will be structured according to the schema
    - If output_schema is None: output will be an unstructured string

    Attributes:
        model_settings: Configuration settings for the model
        stream: Whether to stream the response
        input_schema: Optional JSON schema for structured input (None for unstructured)
        output_schema: Optional JSON schema for structured output (None for unstructured)
        messages: List of messages to provide context (can include system/developer roles)
        input_data: Input data (Dict for structured, str for unstructured)
    """

    model_settings: ModelSettings = Field(default_factory=ModelSettings)
    stream: bool = Field(default=False, description="Enable streaming response")
    input_schema: Optional[Dict[str, Any]] = Field(
        None, description="JSON schema for structured input (None for unstructured)"
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        None, description="JSON schema for structured output (None for unstructured)"
    )
    messages: List[Message] = Field(
        default_factory=list, description="Conversation messages (can include system/developer messages)"
    )
    input_data: Optional[Union[Dict[str, Any], str]] = Field(
        None, description="Input data (Dict for structured, str for unstructured)"
    )
    output_validation_prompt: Optional[str] = Field(
        None,
        description="Natural language validation rules for output (only for Pydantic models in non-streaming mode)",
    )
    input_validation_prompt: Optional[str] = Field(
        None,
        description="Natural language validation rules for input (only for structured input with Pydantic models)",
    )
    llm_retry_limit: Optional[int] = Field(
        default=3, ge=0, description="Number of LLM retries when validation fails (non-streaming only)"
    )
    enable_tools: bool = Field(
        default=False, description="Enable tool calling capability (requires allow_multiple_calls=true)"
    )
    allow_multiple_calls: bool = Field(
        default=True,
        description="Allow multiple LLM calls for retries and tool usage. When false, only a single LLM call is made",
    )
    system_prompt_role: Optional[Literal["system", "developer", "user"]] = Field(
        None,
        description="Role for system prompts in OpenAI models. 'developer' only works with compatible models (not o1-mini)",
    )


class PromptCleanupItem(BaseModel):
    """Item for cleanup request."""

    prompt_id: str = Field(..., description="Prompt identifier")
    version: Optional[int] = Field(default=1, description="Version number (defaults to 1)")


class PromptCleanupRequest(BaseModel):
    """Request for triggering prompt cleanup."""

    prompts: List[PromptCleanupItem] = Field(
        ..., description="List of prompts to cleanup with prompt_id and optional version"
    )
    debug: bool = Field(
        default=True,
        description="Run cleanup synchronously (true) or via workflow (false). Defaults to true",
    )


class OAuthInitiateRequest(BaseModel):
    """Request schema for OAuth flow initiation."""

    prompt_id: str = Field(..., description="Prompt ID (UUID or draft ID)")
    connector_id: str = Field(..., description="Connector ID to initiate OAuth for")
    version: Optional[int] = Field(default=1, ge=1, description="Version of prompt config (defaults to 1)")


class OAuthInitiateResponse(SuccessResponse):
    """Response schema for OAuth initiation."""

    authorization_url: str = Field(..., description="OAuth authorization URL to redirect user to")
    state: str = Field(..., description="OAuth state parameter for security")
    expires_in: int = Field(..., description="State expiration time in seconds")
    gateway_id: str = Field(..., description="Gateway ID used for OAuth flow")


class OAuthStatusResponse(SuccessResponse):
    """Response schema for OAuth status check."""

    oauth_enabled: bool = Field(..., description="Whether OAuth is enabled for this gateway")
    grant_type: str = Field(..., description="OAuth grant type (e.g., 'authorization_code')")
    client_id: str = Field(..., description="OAuth client ID")
    scopes: List[str] = Field(..., description="List of OAuth scopes")
    authorization_url: str = Field(..., description="OAuth authorization endpoint URL")
    redirect_uri: str = Field(..., description="OAuth callback/redirect URI")
    status_message: str = Field(..., description="Status message from MCP Foundry")


class OAuthFetchToolsRequest(BaseModel):
    """Request schema for fetching tools after OAuth."""

    prompt_id: str = Field(..., description="Prompt ID (UUID or draft ID)")
    connector_id: str = Field(..., description="Connector ID to fetch tools for")
    version: Optional[int] = Field(default=1, ge=1, description="Version of prompt config (defaults to 1)")


class OAuthCallbackRequest(BaseModel):
    """Request schema for OAuth callback."""

    code: str = Field(..., description="Authorization code from OAuth provider")
    state: str = Field(..., description="State parameter from OAuth flow")


class OAuthCallbackResponse(SuccessResponse):
    """Response schema for OAuth callback."""

    gateway_id: str = Field(..., description="Gateway ID")
    user_id: str = Field(..., description="User ID/email")
    expires_at: str = Field(..., description="Token expiration timestamp")


class CreatePromptWorkflowRequest(BaseModel):
    """Create prompt workflow request schema."""

    step_number: int = Field(..., gt=0)
    trigger_workflow: bool = False

    workflow_id: UUID4 | None = None
    workflow_total_steps: int | None = None

    project_id: UUID4 | None = None
    endpoint_id: UUID4 | None = None
    name: str | None = None
    description: str | None = None
    tags: list[Tag] | None = None
    prompt_type: PromptTypeEnum | None = None
    auto_scale: bool | None = None
    caching: bool | None = None
    concurrency: list[int] | None = None  # [min, max]
    rate_limit: bool = Field(default=False, description="Enable or disable rate limiting")
    rate_limit_value: Optional[int] = Field(None, ge=1, description="Rate limit value (requests per minute)")
    bud_prompt_id: str | None = None
    discarded_prompt_ids: Optional[List[PromptCleanupItem]] = Field(
        None, description="List of temporary prompt IDs discarded by user that need cleanup"
    )
    client_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Arbitrary metadata from client for UI state preservation"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """Validate and transform name."""
        if v is None:
            return None

        # Replace spaces with hyphens
        v = v.replace(" ", "-")

        # Define allowed pattern: alphanumeric, hyphens
        pattern = r"^[a-zA-Z0-9-]+$"

        if not re.match(pattern, v):
            raise ValueError("Prompt name can only contain letters, numbers, hyphens (-)")

        # strip leading and trailing hyphens and spaces convert it to lowercase
        v = v.strip("- ").lower()

        return v

    @model_validator(mode="after")
    def validate_fields(self):
        # Validate workflow_total_steps when workflow_id is not provided
        if self.workflow_id is None and self.workflow_total_steps is None:
            raise ValueError("workflow_total_steps is required when workflow_id is not provided")

        # Validate rate_limit_value when rate_limit is enabled
        if self.rate_limit and not self.rate_limit_value:
            raise ValueError("rate_limit_value is required when rate_limit is enabled")

        # Validate concurrency array length and values
        if self.concurrency is not None:
            if len(self.concurrency) != 2:
                raise ValueError("Concurrency must be a list of 2 integers [min, max]")
            if self.concurrency[0] >= self.concurrency[1]:
                raise ValueError("Concurrency min must be less than max")

        return self


class CreatePromptWorkflowSteps(BaseModel):
    """Create prompt workflow steps request schema."""

    project_id: UUID4 | None = None
    endpoint_id: UUID4 | None = None
    model_id: UUID4 | None = None
    cluster_id: UUID4 | None = None
    name: str | None = None
    description: str | None = None
    tags: list[Tag] | None = None
    prompt_type: PromptTypeEnum | None = None
    auto_scale: bool | None = None
    caching: bool | None = None
    concurrency: list[int] | None = None  # [min, max]
    rate_limit: bool = Field(default=False, description="Enable or disable rate limiting")
    rate_limit_value: Optional[int] = Field(None, ge=1, description="Rate limit value (requests per minute)")
    bud_prompt_id: str | None = None
    discarded_prompt_ids: Optional[List[PromptCleanupItem]] = Field(
        None, description="List of temporary prompt IDs to cleanup"
    )
    client_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Arbitrary metadata from client for UI state preservation"
    )


class EditPromptRequest(BaseModel):
    """Edit prompt request schema."""

    name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="Name of the prompt, must be non-empty and at most 255 characters.",
    )
    description: str | None = Field(None, description="Description of the prompt.")
    tags: list[Tag] | None = Field(None, description="Tags associated with the prompt.")
    default_version_id: UUID4 | None = Field(None, description="Default version ID for the prompt.")

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        """Ensure the name is not empty or only whitespace."""
        if value is not None and not value.strip():
            raise ValueError("Prompt name cannot be empty or only whitespace.")
        return value


class PromptVersionResponse(BaseModel):
    """Prompt version response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    version: int
    endpoint: EndpointResponse
    model: ModelResponse
    cluster: ClusterResponse | None = None
    created_at: datetime
    modified_at: datetime


class PromptResponse(BaseModel):
    """Prompt response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    description: str | None
    tags: list[dict] | None
    project: ProjectResponse
    prompt_type: str
    auto_scale: bool
    caching: bool
    concurrency: list[int] | None
    rate_limit: bool
    rate_limit_value: int | None
    default_version: PromptVersionResponse
    status: str
    created_at: datetime
    modified_at: datetime
    created_by: UUID4


class SinglePromptResponse(SuccessResponse):
    """Single prompt response."""

    prompt: PromptResponse


class CreatePromptVersionRequest(BaseModel):
    """Create prompt version request schema."""

    endpoint_id: UUID4 = Field(..., description="Endpoint ID for the prompt version")
    bud_prompt_id: str = Field(..., description="Temporary prompt ID from budprompt service")
    set_as_default: bool = Field(default=False, description="Set this version as the default version")


class EditPromptVersionRequest(BaseModel):
    """Edit prompt version request schema."""

    endpoint_id: UUID4 | None = Field(None, description="Endpoint ID for the prompt version")
    set_as_default: bool | None = Field(None, description="Set this version as the default version")


class SinglePromptVersionResponse(SuccessResponse):
    """Single prompt version response."""

    version: PromptVersionResponse


class SchemaBase(BaseModel):
    """Base schema for input/output with validations."""

    schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema representation")
    validations: Optional[Dict[str, Dict[str, str]]] = Field(
        None,
        description="Validation prompts by model and field. Format: {ModelName: {field_name: validation_prompt}}",
    )

    @field_validator("validations")
    @classmethod
    def validate_validations_structure(
        cls, v: Optional[Dict[str, Dict[str, str]]]
    ) -> Optional[Dict[str, Dict[str, str]]]:
        """Validate that validations have proper nested structure."""
        # Allow None values
        if v is None:
            return v

        if isinstance(v, dict):
            for model_name, fields in v.items():
                if not isinstance(model_name, str) or not model_name.strip():
                    raise ValueError(f"Model name must be a non-empty string, got: {model_name}")

                if not isinstance(fields, dict):
                    raise ValueError(f"Validations for model '{model_name}' must be a dictionary of fields")

                for field_name, prompt in fields.items():
                    if not isinstance(field_name, str) or not field_name.strip():
                        raise ValueError(f"Field name in model '{model_name}' must be a non-empty string")

                    if not isinstance(prompt, str) or not prompt.strip():
                        raise ValueError(
                            f"Validation prompt for '{model_name}.{field_name}' must be a non-empty string"
                        )

        return v


class PromptSchemaRequest(BaseModel):
    """Schema for prompt schema validation request.

    This request model supports structured schemas with validation prompts.
    The type field specifies whether this is an input or output schema.
    """

    step_number: int = Field(..., gt=0)
    trigger_workflow: bool = False

    workflow_id: UUID4 | None = None
    workflow_total_steps: int | None = None

    prompt_id: str | None = None
    version: int | None = None
    set_default: bool | None = None
    schema: SchemaBase | None = None
    type: Literal["input", "output"] | None = None
    deployment_name: str | None = None
    permanent: bool = Field(
        default=False,
        description="Store configuration permanently without expiration (default: False, uses configured TTL)",
    )

    @model_validator(mode="after")
    def validate_fields(self):
        # Validate workflow_total_steps when workflow_id is not provided
        if self.workflow_id is None and self.workflow_total_steps is None:
            raise ValueError("workflow_total_steps is required when workflow_id is not provided")

        return self


class PromptSchemaWorkflowSteps(BaseModel):
    """Prompt schema workflow steps request schema."""

    prompt_id: str | None = None
    version: int | None = None
    set_default: bool | None = None
    schema: SchemaBase | None = None
    type: Literal["input", "output"] | None = None
    deployment_name: str | None = None
    permanent: bool | None = None


class PromptConfigRequest(BaseModel):
    """Request model for prompt configuration.

    This request allows clients to save or update prompt configurations in Redis.
    Configurations can be partially updated - only provided fields will be updated.
    """

    prompt_id: Optional[str] = Field(
        None,
        description="Unique identifier for the prompt configuration. If not provided, will be auto-generated.",
    )
    version: int = Field(default=1, ge=1, description="Version of the configuration to save (defaults to 1)")
    set_default: bool = Field(False, description="Whether to set this version as the default (defaults to False)")
    deployment_name: Optional[str] = Field(None, min_length=1, description="Model deployment name")
    model_settings: Optional[ModelSettings] = Field(None, description="Model settings configuration")
    stream: Optional[bool] = Field(None, description="Enable streaming response")
    messages: Optional[List[Message]] = Field(
        None, description="Conversation messages (can include system/developer messages)"
    )
    llm_retry_limit: Optional[int] = Field(
        None, ge=0, description="Number of LLM retries when validation fails (non-streaming only)"
    )
    enable_tools: Optional[bool] = Field(
        None, description="Enable tool calling capability (requires allow_multiple_calls=true)"
    )
    allow_multiple_calls: Optional[bool] = Field(
        None,
        description="Allow multiple LLM calls for retries and tool usage. When false, only a single LLM call is made",
    )
    system_prompt_role: Optional[Literal["system", "developer", "user"]] = Field(
        None,
        description="Role for system prompts in OpenAI models. 'developer' only works with compatible models (not o1-mini)",
    )
    system_prompt: Optional[str] = Field(None, description="System prompt with Jinja2 template support")
    permanent: bool = Field(
        default=False,
        description="Store configuration permanently without expiration (default: False, uses configured TTL)",
    )
    client_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Client-provided metadata for custom tracking and identification",
    )


class PromptConfigResponse(SuccessResponse):
    """Response model for prompt configuration."""

    bud_prompt_id: str = Field(..., description="The unique identifier for the prompt configuration from budprompt")
    bud_prompt_version: int = Field(..., ge=1, description="The version of the prompt configuration from budprompt")


class MCPToolConfig(BaseModel):
    """MCP Tool configuration stored in prompt config."""

    type: Literal["mcp"] = "mcp"
    server_label: Optional[str] = Field(None, description="Virtual server name")
    server_description: Optional[str] = Field(None, description="Server description")
    server_url: Optional[str] = Field(None, description="Server URL")
    require_approval: Literal["always", "never", "auto"] = Field(
        default="never", description="Tool approval requirement"
    )
    allowed_tools: List[str] = Field(default_factory=list, description="List of tool IDs allowed")
    connector_id: Optional[str] = Field(None, description="Virtual server ID from MCP Foundry")
    gateway_config: Dict[str, str] = Field(
        default_factory=dict, description="Gateway configuration with connector_id as key and gateway_id as value"
    )
    gateway_slugs: Dict[str, str] = Field(
        default_factory=dict, description="Gateway slugs with connector_id as key and gateway_slug as value"
    )
    server_config: Dict[str, List[str]] = Field(
        default_factory=dict, description="Server configuration with connector_id as key and list of tool IDs as value"
    )


class PromptConfigurationData(BaseModel):
    """Schema for prompt configuration data retrieved from budprompt."""

    deployment_name: Optional[str] = Field(None, description="Model deployment name")
    model_settings: Optional[ModelSettings] = Field(None, description="Model settings")
    stream: Optional[bool] = Field(None, description="Enable streaming response")
    input_schema: Optional[Dict[str, Any]] = Field(
        None, description="JSON schema for structured input (None for unstructured)"
    )
    input_validation: Optional[Dict[str, Any]] = Field(
        None,
        description="Generated validation codes for input schema",
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        None, description="JSON schema for structured output (None for unstructured)"
    )
    output_validation: Optional[Dict[str, Any]] = Field(
        None,
        description="Generated validation codes for output schema",
    )
    messages: Optional[List[Message]] = Field(
        None, description="Conversation messages (can include system/developer messages)"
    )
    llm_retry_limit: Optional[int] = Field(
        None, description="Number of LLM retries when validation fails (non-streaming only)"
    )
    enable_tools: Optional[bool] = Field(
        None, description="Enable tool calling capability (requires allow_multiple_calls=true)"
    )
    allow_multiple_calls: Optional[bool] = Field(
        None,
        description="Allow multiple LLM calls for retries and tool usage. When false, only a single LLM call is made",
    )
    system_prompt_role: Optional[Literal["system", "developer", "user"]] = Field(
        None,
        description="Role for system prompts in OpenAI models. 'developer' only works with compatible models (not o1-mini)",
    )
    system_prompt: Optional[str] = Field(None, description="System prompt with Jinja2 template support")
    tools: List[MCPToolConfig] = Field(default_factory=list, description="MCP tool configurations")
    client_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Client-provided metadata for custom tracking and identification",
    )


class GetPromptVersionResponse(SuccessResponse):
    """Get prompt version response with configuration data."""

    version: PromptVersionResponse
    config_data: PromptConfigurationData


class PromptConfigGetResponse(SuccessResponse):
    """Response model for getting prompt configuration.

    Returns the complete prompt configuration data stored in Redis.
    """

    prompt_id: str = Field(..., description="The unique identifier for the prompt configuration")
    version: int = Field(..., description="The version number of the configuration retrieved")
    data: PromptConfigurationData = Field(..., description="The prompt configuration data")


class PromptConfigCopyRequest(BaseModel):
    """Request model for copying prompt configuration from budprompt."""

    source_prompt_id: str = Field(..., description="Source prompt ID to copy from")
    source_version: int = Field(..., ge=1, description="Source version number to copy")
    target_prompt_id: str = Field(..., description="Target prompt ID to copy to")
    target_version: int = Field(..., ge=1, description="Target version number to save as")
    replace: bool = Field(
        True, description="If true, replace entire target config. If false, merge only fields present in source"
    )
    set_as_default: bool = Field(True, description="Whether to set the copied version as default for target prompt")


class BudPromptConfig(BaseModel):
    """BudPrompt provider config for prompt execution."""

    type: str = "budprompt"
    api_base: str
    model_name: str  # This will be the prompt name
    api_key_location: str = "dynamic::authorization"


class ConnectorListItem(BaseModel):
    """Schema for individual connector item in list."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    icon: Optional[str] = None
    category: Optional[str] = None
    url: str
    provider: str
    description: Optional[str] = None
    documentation_url: Optional[str] = None


class ConnectorListResponse(PaginatedSuccessResponse):
    """Connector list response schema."""

    model_config = ConfigDict(extra="ignore")

    connectors: list[ConnectorListItem] = []


class ConnectorFilter(BaseModel):
    """Filter schema for connector list API."""

    name: str | None = None
    prompt_id: Optional[str] = Field(None, description="Prompt ID to filter registered/non-registered connectors")
    is_registered: Optional[bool] = Field(None, description="Filter by registration status (requires prompt_id)")


class Connector(BaseModel):
    """Internal schema for full connector data."""

    id: str
    name: str
    icon: Optional[str] = None
    category: Optional[str] = None
    url: str
    provider: str
    description: Optional[str] = None
    documentation_url: Optional[str] = None
    auth_type: ConnectorAuthTypeEnum
    credential_schema: List[Dict[str, Any]]


class ConnectorResponse(SuccessResponse):
    """Response schema for single connector retrieval."""

    model_config = ConfigDict(extra="ignore")

    connector: Connector


class Tool(BaseModel):
    """Schema for tool data."""

    id: UUID4
    name: str
    description: str
    type: str
    schema: Dict[str, Any]


class ToolListItem(BaseModel):
    """Schema for tool item in list response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    name: str
    type: str
    is_added: bool = Field(..., description="Whether tool is added to prompt config")


class ToolFilter(BaseModel):
    """Filter schema for tool list API."""

    prompt_id: str = Field(..., description="Prompt ID to filter tools (UUID or draft ID)")
    connector_id: str = Field(..., description="Connector ID to filter tools")
    version: Optional[int] = Field(default=1, ge=1, description="Version of prompt config (defaults to 1)")


class ToolListResponse(PaginatedSuccessResponse):
    """Tool list response schema."""

    model_config = ConfigDict(extra="ignore")

    tools: list[ToolListItem] = []


class ToolResponse(SuccessResponse):
    """Response schema for single tool retrieval."""

    model_config = ConfigDict(extra="ignore")

    tool: Tool


class PassthroughHeadersMixin(BaseModel):
    """Mixin for passthrough_headers field (common across all auth types)."""

    passthrough_headers: Optional[List[str]] = Field(
        None, description="List of headers to pass through (e.g., ['Authorization', 'X-Tenant-Id'])"
    )


class OAuthCredentials(PassthroughHeadersMixin):
    """OAuth authentication credentials."""

    grant_type: Literal["client_credentials", "authorization_code"] = Field(..., description="OAuth grant type")
    client_id: str = Field(..., min_length=1, description="OAuth client ID")
    client_secret: str = Field(..., min_length=1, description="OAuth client secret")
    token_url: str = Field(..., description="OAuth token endpoint URL")
    authorization_url: str = Field(..., description="OAuth authorization endpoint URL")
    redirect_uri: str = Field(..., description="OAuth callback/redirect URI")
    scopes: Optional[List[str]] = Field(None, description="List of OAuth scopes (e.g., ['repo', 'read:user'])")


class HeadersCredentials(PassthroughHeadersMixin):
    """Headers-based authentication credentials."""

    auth_headers: List[Dict[str, str]] = Field(
        ...,
        min_length=1,
        description="Authentication headers as list of dicts with 'key' and 'value' (e.g., [{'key': 'Authorization', 'value': 'Bearer token'}])",
    )

    @field_validator("auth_headers")
    @classmethod
    def validate_auth_headers(cls, v: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Validate each header has 'key' and 'value' fields."""
        for i, header in enumerate(v):
            if "key" not in header or "value" not in header:
                raise ValueError(f"Header at index {i} must have 'key' and 'value' fields")
            if not header["key"] or not header["value"]:
                raise ValueError(f"Header at index {i} must have non-empty 'key' and 'value'")
        return v


class OpenCredentials(PassthroughHeadersMixin):
    """Open authentication (no auth required)."""

    pass  # Only inherits passthrough_headers


class RegisterConnectorRequest(BaseModel):
    """Request schema for registering a connector to a prompt with auth type-specific credentials."""

    credentials: Union[OAuthCredentials, HeadersCredentials, OpenCredentials] = Field(
        ..., description="Credentials matching connector's auth_type"
    )
    version: int = Field(default=1, ge=1, description="Version of prompt config (defaults to 1)")
    permanent: bool = Field(
        default=False,
        description="Store configuration permanently without expiration (default: False, uses configured TTL)",
    )


class AddToolRequest(BaseModel):
    """Request schema for adding tools to a prompt."""

    prompt_id: str = Field(..., description="Prompt ID (must exist in Redis)")
    connector_id: str = Field(..., description="Connector ID")
    tool_ids: List[UUID] = Field(
        ..., description="Tool IDs to add/update (empty list removes all tools for this connector)"
    )
    version: int = Field(default=1, ge=1, description="Prompt config version (defaults to 1)")
    permanent: bool = Field(
        default=False,
        description="Store configuration permanently without expiration (default: False, uses configured TTL)",
    )


class AddToolResponse(SuccessResponse):
    """Response schema for adding tools."""

    model_config = ConfigDict(extra="ignore")

    virtual_server_id: str = Field(..., description="Virtual server ID from MCP Foundry")
    virtual_server_name: str = Field(..., description="Virtual server name (format: {prompt_id}__v{version})")
    added_tools: List[str] = Field(..., description="List of added tool IDs")


class GatewayResponse(BaseModel):
    """Response from MCP Foundry gateway creation."""

    gateway_id: str = Field(..., description="Gateway ID from MCP Foundry")
    name: str = Field(..., description="Gateway name (format: {prompt_id}__v{version}__{connector_id})")
    url: str
    transport: str
    visibility: str
    created_at: Optional[datetime] = None


class RegisterConnectorResponse(SuccessResponse):
    """Response schema for connector registration.

    Gateway name format: {prompt_id}__v{version}__{connector_id}
    Each prompt version gets its own gateway for proper version isolation.
    """

    gateway: GatewayResponse
    connector_id: str
    budprompt_id: str


class DisconnectConnectorResponse(SuccessResponse):
    """Response schema for disconnecting connector."""

    model_config = ConfigDict(extra="ignore")

    prompt_id: str = Field(..., description="Prompt ID")
    connector_id: str = Field(..., description="Disconnected connector ID")
    deleted_gateway_id: str = Field(..., description="Deleted gateway ID")


class TraceEvent(BaseModel):
    """Schema for span events."""

    timestamp: datetime
    name: str
    attributes: Dict[str, str]


class TraceLink(BaseModel):
    """Schema for span links."""

    trace_id: str
    span_id: str
    trace_state: str
    attributes: Dict[str, str]


class TraceItem(BaseModel):
    """Schema for a single trace/span item."""

    timestamp: datetime
    trace_id: str
    span_id: str
    parent_span_id: str
    trace_state: str
    span_name: str
    span_kind: str
    service_name: str
    resource_attributes: Dict[str, str]
    scope_name: str
    scope_version: str
    span_attributes: Dict[str, str]
    duration: int  # nanoseconds
    status_code: str
    status_message: str
    events: List[TraceEvent]
    links: List[TraceLink]
    child_span_count: int = 0  # Number of child spans for this trace

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})


class TraceListResponse(PaginatedSuccessResponse):
    """Response schema for listing traces."""

    object: str = "trace_list"
    items: List[TraceItem] = []


class TraceDetailResponse(SuccessResponse):
    """Response schema for single trace with all spans."""

    object: str = "trace_detail"
    trace_id: str
    spans: List[TraceItem] = []
    total_spans: int = 0
