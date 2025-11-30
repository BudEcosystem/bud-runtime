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

"""Schemas for responses module - OpenAI-compatible API."""

from typing import Any, Dict, List, Optional, Union

from openai.types.responses import Response, ResponseInputItem, ResponsePromptParam
from openai.types.responses.response_prompt_param import Variables
from pydantic import BaseModel, Field, field_serializer


class OpenAIResponse(Response):
    """Custom Response that serializes created_at as int instead of float.

    This extends OpenAI's official Response type and overrides the created_at
    field serialization to output integers instead of floats, providing a
    cleaner API response format while maintaining internal compatibility.
    """

    @field_serializer("created_at")
    def serialize_created_at(self, value: float) -> int:
        """Convert created_at from float to int during JSON serialization.

        Args:
            value: The created_at timestamp as float (Unix timestamp)

        Returns:
            Integer representation of the timestamp
        """
        return int(value)


class BudResponsePromptParam(ResponsePromptParam):
    """Extended ResponsePromptParam that supports Variables + any value types.

    Inherits from OpenAI's ResponsePromptParam but overrides the variables field
    to accept both the standard Variables types AND any additional Python types.
    """

    variables: Optional[Dict[str, Union[Variables, Any]]]
    """Optional map of values to substitute in for variables in your prompt.

    Values can be:
    - OpenAI Variables types: str, ResponseInputTextParam, ResponseInputImageParam, ResponseInputFileParam
    - Any other type: int, float, bool, None, dict, list, etc.
    """


class ResponseCreateRequest(BaseModel):
    """Request model for creating responses via OpenAI-compatible API.

    This model follows OpenAI's responses API structure for 100% compatibility.
    """

    prompt: Optional[BudResponsePromptParam] = Field(
        ..., description="Prompt template reference with id, optional variables, and version"
    )
    input: Union[str, List[ResponseInputItem]] = Field(
        None,
        description="Text input to the model. Can be a simple string or array of message objects. "
        "String format: 'What is 2+2?' | "
        "Array format: [{'role': 'user', 'content': 'Hello'}, ...]",
    )


class OpenAIError(BaseModel):
    """OpenAI-compatible error details."""

    message: str = Field(..., description="Error message description")
    type: str = Field(..., description="Error type based on HTTP status (e.g., bad_request, not_found)")
    param: Optional[str] = Field(
        None, description="Parameter path that caused the error (e.g., prompt.variables.amount)"
    )
    code: Optional[str] = Field(None, description="Specific error code (e.g., invalid_type, required)")


class OpenAIResponsesError(BaseModel):
    """OpenAI-compatible error response format for responses API."""

    error: OpenAIError = Field(..., description="Error details in OpenAI format")
