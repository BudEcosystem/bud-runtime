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

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator, model_validator

from ..cluster_ops.schemas import ClusterResponse
from ..commons.constants import (
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
    top_p: float = Field(default=0.9, ge=0.0, le=1.0, description="Nucleus sampling parameter")
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
    cluster: ClusterResponse
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


class PromptConfigResponse(SuccessResponse):
    """Response model for prompt configuration."""

    bud_prompt_id: str = Field(..., description="The unique identifier for the prompt configuration from budprompt")
    bud_prompt_version: int = Field(..., ge=1, description="The version of the prompt configuration from budprompt")


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


class PromptConfigGetResponse(SuccessResponse):
    """Response model for getting prompt configuration.

    Returns the complete prompt configuration data stored in Redis.
    """

    prompt_id: str = Field(..., description="The unique identifier for the prompt configuration")
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
