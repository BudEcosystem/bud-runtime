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

from typing import Any, Dict, List, Optional, Union

from budmicroframe.commons.schemas import SuccessResponse
from pydantic import BaseModel, Field


class ModelSettings(BaseModel):
    """Model settings for LLM configuration.

    Attributes:
        temperature: Controls randomness in the model's output (0-2)
        max_tokens: Maximum number of tokens to generate
        top_p: Controls diversity of the output (0-1)
        frequency_penalty: Penalizes frequently used tokens (-2 to 2)
        presence_penalty: Penalizes tokens based on presence in the text (-2 to 2)
        stop_sequences: List of sequences where the model will stop generating
        seed: Random seed for reproducibility
    """

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, gt=0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    stop_sequences: List[str] = Field(default_factory=list)
    seed: Optional[int] = None


class Message(BaseModel):
    """Message structure for prompt execution.

    Attributes:
        role: The role of the message sender (user, assistant, system)
        content: The content of the message
    """

    role: str = Field(default="user")
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


class PromptExecuteResponse(SuccessResponse):
    """Response model for prompt execution.

    Attributes:
        success: Whether the execution was successful
        data: The generated output data (Dict for structured, str for unstructured)
        error: Error message if execution failed
        metadata: Additional metadata about the execution
    """

    data: Optional[Union[Dict[str, Any], str]] = Field(
        None, description="Generated output (Dict for structured, str for unstructured)"
    )
