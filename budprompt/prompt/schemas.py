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

from typing import Any, Dict, List, Literal, Optional, Union

from budmicroframe.commons.schemas import SuccessResponse
from pydantic import BaseModel, Field


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
        role: The role of the message sender (user, assistant, developer)
        content: The content of the message
    """

    role: Literal["user", "assistant", "developer"] = Field(default="user")
    content: str = Field(..., min_length=1)


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
        system_prompt: System prompt to guide the model's behavior
        messages: List of messages to provide context
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
    system_prompt: str = Field(..., min_length=1, description="System prompt for the model")
    messages: List[Message] = Field(default_factory=list, description="Conversation messages")
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
