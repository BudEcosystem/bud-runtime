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

"""Pydantic schemas for the prompt module."""

import time
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from budmicroframe.commons.schemas import CloudEventBase, ResponseBase, SuccessResponse
from budmicroframe.commons.types import lowercase_string
from pydantic import BaseModel, Field, field_validator


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
    allowed_tool_names: List[str] = Field(default_factory=list, description="List of tool IDs allowed")
    connector_id: Optional[str] = Field(None, description="Virtual server ID from MCP Foundry")
    gateway_config: Dict[str, str] = Field(
        default_factory=dict, description="Gateway configuration with connector_id as key and gateway_id as value"
    )
    server_config: Dict[str, List[str]] = Field(
        default_factory=dict, description="Server configuration with connector_id as key and list of tool IDs as value"
    )


class PromptExecuteRequest(BaseModel):
    """Request model for prompt execution.

    Supports both structured and unstructured inputs/outputs:
    - If input_schema is provided: input_data should be a Dict matching the schema
    - If input_schema is None: input_data should be a string (unstructured)
    - If output_schema is provided: output will be structured according to the schema
    - If output_schema is None: output will be an unstructured string

    Attributes:
        deployment_name: Name of the model deployment to use
        model_settings: Configuration settings for the model
        stream: Whether to stream the response
        input_schema: Optional JSON schema for structured input (None for unstructured)
        output_schema: Optional JSON schema for structured output (None for unstructured)
        messages: List of messages to provide context (can include system/developer roles)
        input_data: Input data (Dict for structured, str for unstructured)
    """

    deployment_name: str = Field(..., min_length=1, description="Model deployment name")
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


class PromptExecuteResponse(SuccessResponse):
    """Response model for prompt execution.

    Attributes:
        success: Whether the execution was successful
        data: The generated output data (any supported type)
        error: Error message if execution failed
        metadata: Additional metadata about the execution
    """

    data: Optional[Any] = Field(
        None, description="Generated output (can be any supported type: dict, str, int, float, bool, list)"
    )


# Revised schemas


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


class PromptConfigurationRequest(CloudEventBase):
    """Schema for prompt configuration stored in prompt_schema field.

    This request model supports structured schemas with validation prompts:
    - input_schema: Contains schema and validations for input data
    - output_schema: Contains schema and validations for output data
    - validations format: {ModelName: {field_name: validation_prompt}}

    Example validations structure:
        {
            "RootModel": {
                "field_1": "validation prompt for field_1",
                "field_2": "validation prompt for field_2"
            },
            "NestedModel": {
                "field_1": "validation prompt for nested field_1"
            }
        }
    """

    deployment_name: str = Field(..., min_length=1, description="Model deployment name")
    model_settings: ModelSettings = Field(default_factory=ModelSettings)
    stream: bool = Field(default=False, description="Enable streaming response")
    input_schema: Optional[SchemaBase] = Field(
        None, description="JSON schema for structured input (None for unstructured)"
    )
    output_schema: Optional[SchemaBase] = Field(
        None, description="JSON schema for structured output (None for unstructured)"
    )
    messages: List[Message] = Field(
        default_factory=list, description="Conversation messages (can include system/developer messages)"
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


class PromptConfigurationResponse(ResponseBase):
    """Response schema for prompt configurations."""

    object: lowercase_string = "prompt_configuration"
    workflow_id: UUID
    created: int = Field(default_factory=lambda: int(time.time()))


class PromptSchemaRequest(CloudEventBase):
    """Schema for prompt schema validation request.

    This request model supports structured schemas with validation prompts.
    The type field specifies whether this is an input or output schema.
    """

    prompt_id: Optional[str] = Field(None, description="Unique identifier for the prompt configuration")
    version: Optional[int] = Field(None, ge=1, description="Version of the configuration to save (defaults to 1)")
    set_default: bool = Field(False, description="Whether to set this version as the default (defaults to False)")
    permanent: bool = Field(
        default=False,
        description="Store configuration permanently without expiration (default: False, uses configured TTL)",
    )
    schema: SchemaBase = Field(None, description="JSON schema for structured input/output (None for unstructured)")
    type: Literal["input", "output"] = Field(..., description="Type of schema - either 'input' or 'output'")
    deployment_name: Optional[str] = Field(None, min_length=1, description="Model deployment name")
    # Fields for API key bypass during validation
    endpoint_id: Optional[str] = Field(None, description="Endpoint ID for API key bypass")
    model_id: Optional[str] = Field(None, description="Model ID for API key bypass")
    project_id: Optional[str] = Field(None, description="Project ID for API key bypass")
    user_id: Optional[str] = Field(None, description="User ID for API key bypass")
    api_key_project_id: Optional[str] = Field(None, description="API key project ID for API key bypass")
    access_token: Optional[str] = Field(None, description="JWT access token to be hashed for API key bypass")


class PromptCleanupItem(BaseModel):
    """Item for cleanup request."""

    prompt_id: str = Field(..., description="Prompt identifier")
    version: Optional[int] = Field(default=1, description="Version number (defaults to 1)")


class PromptCleanupRequest(CloudEventBase):
    """Request for MCP cleanup endpoint."""

    prompts: Optional[List[PromptCleanupItem]] = Field(
        default_factory=list, description="Prompts to cleanup. None/empty = cleanup expired prompts"
    )


class PromptSchemaResponse(ResponseBase):
    """Response schema for prompt schema validation."""

    object: lowercase_string = "prompt_schema"
    workflow_id: UUID
    prompt_id: str = Field(..., description="Unique identifier for the prompt configuration")
    version: int | str = Field(..., description="The version of the prompt configuration that was saved")
    created: int = Field(default_factory=lambda: int(time.time()))


class PromptCleanupResponse(ResponseBase):
    """Response schema for prompt cleanup."""

    object: lowercase_string = "prompt_cleanup"
    workflow_id: UUID
    cleaned: List[Dict[str, Any]] = Field(default_factory=list, description="Successfully cleaned prompts")
    failed: List[Dict[str, Any]] = Field(default_factory=list, description="Failed cleanup prompts")
    created: int = Field(default_factory=lambda: int(time.time()))


class PromptConfigurationData(BaseModel):
    """Schema for prompt configuration."""

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
    tools: List[MCPToolConfig] = Field(
        default_factory=list,
        description="List of tool configurations (MCP tools) for this prompt",
    )


class MCPCleanupRegistryEntry(BaseModel):
    """Single cleanup entry in the common registry for MCP resource cleanup.

    Note: prompt_key is used as the dictionary key in the registry, not stored in the entry.
    """

    prompt_id: str = Field(..., description="Prompt identifier")
    version: int = Field(..., description="Version number")
    created_at: str = Field(..., description="ISO 8601 timestamp when first created")
    expires_at: str = Field(..., description="ISO 8601 timestamp when expires")
    cleanup_failed: bool = Field(default=False, description="Flag if cleanup failed")
    reason: Optional[str] = Field(None, description="Error reason if cleanup failed")
    mcp_resources: Dict[str, Any] = Field(..., description="MCP resource IDs to cleanup")


class PromptExecuteData(BaseModel):
    """Schema for prompt configuration."""

    deployment_name: str = Field(..., min_length=1, description="Model deployment name")
    model_settings: ModelSettings = Field(default_factory=ModelSettings)
    stream: bool = Field(default=False, description="Enable streaming response")
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
    messages: List[Message] = Field(
        default_factory=list, description="Conversation messages (can include system/developer messages)"
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
    tools: List[MCPToolConfig] = Field(
        default_factory=list,
        description="List of tool configurations (MCP tools) for this prompt",
    )


class PromptConfigRequest(BaseModel):
    """Request model for prompt configuration.

    This request allows clients to save or update prompt configurations in Redis.
    Configurations can be partially updated - only provided fields will be updated.
    """

    prompt_id: Optional[str] = Field(
        None,
        description="Unique identifier for the prompt configuration. If not provided, will be auto-generated.",
    )
    version: Optional[int] = Field(None, ge=1, description="Version of the configuration to save (defaults to 1)")
    set_default: bool = Field(False, description="Whether to set this version as the default (defaults to False)")
    permanent: bool = Field(
        default=False,
        description="Store configuration permanently without expiration (default: False, uses configured TTL)",
    )
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
    tools: List[MCPToolConfig] = Field(
        default_factory=list,
        description="List of tool configurations (MCP tools) to add/update",
    )


class PromptConfigResponse(SuccessResponse):
    """Response model for prompt configuration."""

    prompt_id: str = Field(..., description="The unique identifier for the prompt configuration")
    version: int = Field(..., description="The version of the prompt configuration that was saved")


class PromptConfigGetResponse(SuccessResponse):
    """Response model for getting prompt configuration.

    Returns the complete prompt configuration data stored in Redis.
    """

    prompt_id: str = Field(..., description="The unique identifier for the prompt configuration")
    version: int = Field(..., description="The version number of the configuration retrieved")
    data: PromptConfigurationData = Field(..., description="The prompt configuration data")


class PromptConfigGetRawResponse(SuccessResponse):
    """Response model for getting raw prompt configuration from Redis.

    Returns the raw JSON data without Pydantic processing or default values.
    """

    prompt_id: str = Field(..., description="The unique identifier for the prompt configuration")
    version: int = Field(..., description="The version number of the configuration retrieved")
    data: Dict[str, Any] = Field(..., description="The raw prompt configuration data from Redis")


class PromptConfigCopyRequest(BaseModel):
    """Request model for copying prompt configuration."""

    source_prompt_id: str = Field(..., description="Source prompt ID to copy from")
    source_version: int = Field(..., ge=1, description="Source version number to copy")
    target_prompt_id: str = Field(..., description="Target prompt ID to copy to")
    target_version: int = Field(..., ge=1, description="Target version number to save as")
    replace: bool = Field(
        True, description="If true, replace entire target config. If false, merge only fields present in source"
    )
    set_as_default: bool = Field(False, description="Whether to set the copied version as default for target prompt")


class PromptConfigCopyResponse(SuccessResponse):
    """Response model for copy prompt configuration."""

    source_prompt_id: str = Field(..., description="Source prompt ID copied from")
    source_version: int = Field(..., description="Source version number copied")
    target_prompt_id: str = Field(..., description="Target prompt ID copied to")
    target_version: int = Field(..., description="Target version number saved as")
    data: PromptConfigurationData = Field(..., description="The final configuration data saved to Redis")
    message: str = Field(default="Prompt configuration copied successfully")


class PromptSetDefaultVersionRequest(BaseModel):
    """Request model for setting default version of prompt configuration."""

    prompt_id: str = Field(..., description="The prompt ID to set default version for")
    version: int = Field(..., ge=1, description="The version number to set as default")


class PromptDeleteRequest(BaseModel):
    """Request model for deleting prompt configuration."""

    prompt_id: str = Field(..., description="The prompt ID to delete")
    version: Optional[int] = Field(
        None, ge=1, description="Specific version to delete (if not provided, deletes all versions)"
    )
